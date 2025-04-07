import socket
import json
import argparse
import time
import uuid

# Basic logging for the dummy peer
def log(message):
    print(f"[Dummy Peer] {message}")

def handle_client(client_socket, client_address, dummy_host, dummy_port):
    """Handles a single incoming client connection."""
    log(f"Connection accepted from {client_address}")
    try:
        # Attempt to receive data (simple blocking receive)
        # Adjust buffer size if you expect very large messages,
        # but for testing basic interactions, 4096 is usually sufficient.
        data = client_socket.recv(4096)

        if not data:
            log(f"Connection closed by {client_address} before sending data.")
            return

        try:
            # Assume one JSON message per connection for simplicity
            message_str = data.decode('utf-8').strip()
            # Handle potential multiple JSON objects sent back-to-back (less likely here)
            # For simplicity, we'll just process the first valid one found.
            try:
                 msg_obj = json.loads(message_str)
            except json.JSONDecodeError as e:
                 # Try to find the first JSON object if multiple were sent or buffer has extra data
                 log(f"Initial JSON decode failed: {e}. Trying to find first valid JSON.")
                 if '}{' in message_str:
                      message_str = message_str.split('}{')[0] + '}'
                 elif message_str.endswith('}'):
                      # Find the start, assumes simple structure
                      start_index = message_str.find('{')
                      if start_index != -1:
                           message_str = message_str[start_index:]
                 else:
                      raise e # Re-raise if it doesn't look like a simple fixable issue

                 msg_obj = json.loads(message_str)


            log(f"Received message: {json.dumps(msg_obj, indent=2)}") # Pretty print

            msg_type = msg_obj.get("type")
            reply = None

            # --- Define Dummy Responses ---
            if msg_type == "GOSSIP":
                gossip_id = msg_obj.get("id", "unknown_gossip_id")
                log(f"Responding to GOSSIP ({gossip_id})")
                reply = {
                    "type": "GOSSIP_REPLY",
                    "host": dummy_host,
                    "port": dummy_port,
                    "peerId": f"dummy-peer-{dummy_port}", # Simple unique ID for the dummy
                    "files": { # Example file list the dummy "has"
                        "dummy_file_id_abc": "example_document.txt",
                        "dummy_file_id_123": "another_file.dat",
                        f"known_{gossip_id[:8]}": "file_related_to_gossip.tmp"
                    }
                }

            elif msg_type == "GET_FILE":
                file_id = msg_obj.get("file_id", "unknown_file_id")
                log(f"Responding to GET_FILE for ID: {file_id}")
                # Simulate having the file
                reply = {
                    "type": "FILE_DATA",
                    "file_name": f"dummy_{file_id}.txt",
                    "file_size": 42,
                    "file_id": file_id,
                    "file_owner": f"dummy-peer-{dummy_port}",
                    "file_timestamp": int(time.time()),
                    "data": f"This is the dummy content for file ID {file_id}. Timestamp: {time.time()}" # Base64 encode if your real app expects it
                }

            # --- Acknowledge other message types (no specific reply needed for dummy) ---
            elif msg_type == "GOSSIP_REPLY":
                log("Acknowledged GOSSIP_REPLY (no reply sent)")
            elif msg_type == "FILE_DATA":
                log("Acknowledged FILE_DATA (no reply sent)")
            elif msg_type == "ANNOUNCE":
                log("Acknowledged ANNOUNCE (no reply sent)")
            elif msg_type == "DELETE":
                log("Acknowledged DELETE (no reply sent)")
            else:
                log(f"Received unknown or unhandled message type: {msg_type}")

            # --- Send Reply if one was generated ---
            if reply:
                try:
                    reply_bytes = json.dumps(reply).encode('utf-8')
                    log(f"Sending reply: {json.dumps(reply)}")
                    client_socket.sendall(reply_bytes)
                    log("Reply sent.")
                except socket.error as e:
                    log(f"Socket error sending reply to {client_address}: {e}")
                except Exception as e:
                     log(f"Unexpected error sending reply: {e}")

        except json.JSONDecodeError:
            log(f"Received invalid/incomplete JSON from {client_address}. Data: {data[:200]}...") # Log start of data
        except UnicodeDecodeError:
             log(f"Could not decode data as UTF-8 from {client_address}. Raw: {data[:200]}...")
        except Exception as e:
            log(f"Error processing message from {client_address}: {e}")

    except socket.timeout:
        log(f"Socket timed out waiting for data from {client_address}")
    except socket.error as e:
        # Handle cases like connection reset
        log(f"Socket error during communication with {client_address}: {e}")
    except Exception as e:
         log(f"Unexpected error handling client {client_address}: {e}")
    finally:
        log(f"Closing connection to {client_address}")
        try:
            client_socket.close()
        except socket.error:
            pass # Ignore errors closing already closed sockets

def start_dummy_peer(host, port):
    """Starts the dummy peer listening server."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Allow reusing the address quickly after shutdown (useful for testing)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((host, port))
        server_socket.listen(5) # Listen for up to 5 queued connections
        log(f"Dummy peer listening on {host}:{port}")

        while True: # Main loop to accept connections
            try:
                # Wait and accept a new connection (blocking)
                client_socket, client_address = server_socket.accept()
                client_socket.settimeout(5.0) # Set a timeout for recv

                # Handle the client connection directly in the main thread
                # (No threading needed for this simple dummy)
                handle_client(client_socket, client_address, host, port)

            except socket.error as e:
                log(f"Error accepting connection: {e}")
                # Avoid busy-looping if accept keeps failing
                time.sleep(0.1)
            except Exception as e:
                 log(f"Unexpected error in accept loop: {e}")


    except OSError as e:
         log(f"FATAL: Could not bind to {host}:{port}. Error: {e}")
         log("Check if the port is already in use or if you have permissions.")
    except KeyboardInterrupt:
        log("Keyboard interrupt received. Shutting down dummy peer...")
    finally:
        log("Closing server socket.")
        server_socket.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple Dummy P2P Peer for Testing")
    parser.add_argument('--host', default='127.0.0.1',
                        help='Host address for the dummy peer to listen on (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, required=True,
                        help='Port number for the dummy peer to listen on')

    args = parser.parse_args()

    start_dummy_peer(args.host, args.port)