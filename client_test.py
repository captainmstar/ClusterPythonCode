import socket

HOST = "localhost"  # The server's hostname or IP address
PORT = 50021  # The port used by the server

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    data = s.recv(1024)
    while True:
        data = s.recv(1024)
        print(f"Received {data!r}")
    s.close()