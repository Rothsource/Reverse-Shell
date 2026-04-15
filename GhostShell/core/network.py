import socket
import subprocess
import sys
import termios
import tty
import os

from core.terminal import read_key


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


def make_server(port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(1)
    return srv


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

    sys.stdout.write(
        f"  \033[1;36m[?]\033[0m Select interface \033[2m(↑↓ arrow + Enter)\033[0m\r\n\r\n"
    )
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
