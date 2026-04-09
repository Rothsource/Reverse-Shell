import socket
import sys
import select
import termios
import tty
import os

HOST = "0.0.0.0"

# Ask for port
port_input = input("Enter port to listen on: ")
try:
    PORT = int(port_input)
except ValueError:
    print("Invalid port. Using default 4444.")
    PORT = 4444

# Create socket
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen(1)

print(f"Listening on {HOST}:{PORT}...")

client_socket, addr = server.accept()
print(f"Connection from {addr}")

# Save terminal settings
fd = sys.stdin.fileno()
old_settings = termios.tcgetattr(fd)

try:
    # Set raw mode
    tty.setraw(fd)

    while True:
        # Monitor stdin and socket
        rlist, _, _ = select.select([sys.stdin, client_socket], [], [])

        for ready in rlist:
            # Incoming data from client
            if ready == client_socket:
                data = client_socket.recv(4096)
                if not data:
                    raise Exception("Connection closed")

                sys.stdout.write(data.decode(errors="ignore"))
                sys.stdout.flush()

            # Keyboard input
            elif ready == sys.stdin:
                char = os.read(fd, 1) # read single char (raw)
                client_socket.send(char.encode())

except Exception as e:
    print(f"\nDisconnected: {e}")

finally:
    # Restore terminal settings
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    client_socket.close()
    server.close()