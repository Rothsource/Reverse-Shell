import sys
from core.terminal import read_key, get_terminal_size


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
