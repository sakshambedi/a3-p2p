import socket
import select
import os
import time
import json

HOST = '127.0.0.1'
PORT = 1234
DATA_DIR = "./server_files"
METADATA_FILE = "./server_files/file_metadata.json"
CHUNK_SIZE = 1024  # Define the size of each chunk

os.makedirs(DATA_DIR, exist_ok=True)

# Load or initialize metadata
if os.path.exists(METADATA_FILE):
    with open(METADATA_FILE, "r") as f:
        file_metadata = json.load(f)
else:
    file_metadata = {}

def save_metadata():
    with open(METADATA_FILE, "w") as f:
        json.dump(file_metadata, f, indent=4)

def receive_file(sock, filepath, username):
    """Receive a file in chunks and save it to the server."""
    print(f"Receiving file {filepath} from {username} on {sock.getpeername()}\n")
    # Receive the file size first
    sock.sendall(b"OK")
    file_size = int(sock.recv(1024).decode())
    print(f"File size: {file_size} bytes\n")
    received_size = 0

    with open(filepath, "wb") as f:
        while received_size < file_size:
            chunk = sock.recv(min(CHUNK_SIZE, file_size - received_size))
            f.write(chunk)
            received_size += len(chunk)

    print(f"File saved: {filepath}")


def send_file(sock, filepath, username):
    """Send a file in chunks to the client."""
    print(f"Sending file {filepath} to {username} on {sock.getpeername()}\n")
    file_size = os.path.getsize(filepath)
    sock.sendall(str(file_size).encode())  # Send the file size first
    print(f"File size: {file_size} bytes\n")
    
    print(sock.recv(1024))  # Receive the client's response
    
    done = False
    with open(filepath, "rb") as f:
        while not done:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                done = True
            else:
                sock.send(chunk)
    print("File sent.\n")

def handle_client(sock, address, clients):
    try:
        data = sock.recv(1024).decode().strip()
        if not data:
            return

        command, *args = data.split(maxsplit=1)
        username = clients.get(sock, None)

        if command == "LOGIN":
            if not args:
                sock.send(b"LOGIN command requires a username.\n")
            else:
                username = args[0]
                clients[sock] = username
                sock.send(f"Logged in as {username}.\n".encode())
                print(f"User {username} logged in from {address}\n")
        elif command == "PUSH":
            if not username:
                sock.send(b"You must login first using LOGIN <username>.\n")
                return
            filename = args[0]
            filepath = os.path.join(DATA_DIR, filename)
            receive_file(sock, filepath, username)

            # Update metadata
            file_size = os.path.getsize(filepath)
            file_metadata[filename] = {
                "owner": username,
                "timestamp": time.ctime(),
                "size": file_size
            }
            save_metadata()
            sock.send(b"File uploaded successfully.\n")

        elif command == "LIST":
            if not username:
                sock.send(b"You must login first using LOGIN <username>.\n")
                return
            if file_metadata:
                response = "\n".join(
                    f"{name} - {meta['size']} bytes - Uploaded by {meta['owner']} on {meta['timestamp']}"
                    for name, meta in file_metadata.items()
                )
                sock.send(response.encode())
            else:
                sock.send(b"No files available.\n")

        elif command == "GET":
            if not username:
                sock.send(b"You must login first using LOGIN <username>.\n")
                return
            filename = args[0]
            filepath = os.path.join(DATA_DIR, filename)
            if os.path.exists(filepath):
                send_file(sock, filepath, username)
            else:
                sock.send(b"File not found.\n")

        elif command == "DELETE":
            if not username:
                sock.send(b"You must login first using LOGIN <username>.\n")
                return
            filename = args[0]
            filepath = os.path.join(DATA_DIR, filename)
            if filename in file_metadata and file_metadata[filename]["owner"] == username:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    del file_metadata[filename]
                    save_metadata()
                    print(f"File {filename} deleted by {username}\n")
                    sock.send(b"File deleted.\n")
                else:
                    sock.send(b"File not found.\n")
            else:
                sock.send(b"Permission denied. You are not the owner of this file.\n")
        else:
            sock.send(b"Unknown command.\n")
    except Exception as e:
        print(f"Error handling client {address}: {e}\n")
        sock.send(b"Error processing request.\n")

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"Server listening on {HOST}:{PORT}\n")

    sockets = [server_socket]
    clients = {}  # Map sockets to usernames

    while True:
        readable, _, _ = select.select(sockets, [], [])
        for s in readable:
            if s is server_socket:
                client_socket, client_address = server_socket.accept()
                print(f"Connection from {client_address}\n")
                sockets.append(client_socket)
            else:
                handle_client(s, client_address, clients)
                if s not in clients:  # If client disconnected, clean up
                    sockets.remove(s)
                    s.close()

if __name__ == "__main__":
    start_server()