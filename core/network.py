import argparse
import json
import socket
import threading
import uuid
import concurrent.futures
import select  # Import the select module
import queue # For potential future use with non-blocking writes
import time # For select timeout

from core.db_manager import DB_Manager
from core.network_tracker import Network_Tracker
from utils.logger import Logger, LoggerClass

logger: LoggerClass = Logger(__name__).get_logger()

class Peer_Protocol:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.db = DB_Manager(args.db_file, args.server_data)
        self.network_tracker = Network_Tracker()
        self.running = True
        self.stop_event = threading.Event() 
        self.listener_socket : None | socket.socket = None
        self.web_server_socket : None | socket.socket = None
        
        
        self.client_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=getattr(args, 'max_connections', 50),
            thread_name_prefix='MsgProcessor' # Renamed for clarity
        )

        self.inputs = [] 
        self.outputs = []         
        self.client_sockets = {} # {socket_fileno: socket_object}

        self.__start()

    def __start(self) -> None:
        try:
            self.start_listener_socket() 
            self.start_internal_listener()
            self.send_initial_gossip()
            self.run_server_loop()
        except KeyboardInterrupt:
             logger.info("Keyboard interrupt received, shutting down.")
        except Exception as e:
            logger.error(f"Failed to start or run peer protocol: {e}", exc_info=True)
        finally:
            self.shutdown()

    def start_listener_socket(self):
        """Initialize the listening socket."""
        host = self.args.host
        port = self.args.port        

        try:
            self.listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)            
            self.listener_socket.bind((host, port))
            self.listener_socket.listen(getattr(self.args, 'listen_backlog', 5))            
            self.inputs.append(self.listener_socket)
            logger.info(f"TCP Listener socket ready on {host}:{port}")

        except Exception as e:
            logger.error(f"Failed to start listener socket: {e}")
            self.cleanup_socket(self.listener_socket) # Use generic cleanup
            raise
    
    
    def start_internal_listener(self):
        internal_host = self.args.host
        internal_port = self.args.port + 1
        if internal_port == self.args.port:
            logger.error("Internal listener port cannot be the same as the P2P port!")
            raise ValueError("Ports conflict")

        try:
            self.web_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.web_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.web_server_socket.bind((internal_host, internal_port))
            self.web_server_socket.listen(5) 
            self.web_server_socket.setblocking(False) 
            self.inputs.append(self.web_server_socket)
            logger.info(f"Web server socket ready on {internal_host}:{internal_port}")
        except Exception as e:
            logger.error(f"Failed to start internal listener socket: {e}")
            # Cleanup logic if needed
            raise


    def cleanup_socket(self, sock: socket.socket, addr_info="listener"):
        """Safely close a socket and remove it from select lists."""
        if sock is None:
            return
        
        if sock in self.inputs:
            self.inputs.remove(sock)
        if sock in self.outputs:
            self.outputs.remove(sock)
        
        if sock.fileno() in self.client_sockets:
            del self.client_sockets[sock.fileno()]

        try:
            sock.close()
        except Exception as e:
            logger.error(f"Error closing socket for {addr_info}: {e}")


    def run_server_loop(self) -> None:
        """Main event loop using select to handle socket I/O."""
        logger.info("Starting select-based server loop...")
        while not self.stop_event.is_set():
            try:                        
                readable, writable, exceptional = select.select(self.inputs, self.outputs, self.inputs)
                for sock in readable:
                    if sock is self.listener_socket:                        
                        self.accept_new_connection(self.listener_socket, source='peer')
                    elif sock is self.web_server_socket: # <--- Renamed for clarity
                        
                        self.accept_new_connection(self.web_server_socket, source='internal') # Use 'internal' or 'web'
                    else:
                        self.handle_readable_client(sock) # existing client connection
                # for sock in readable:
                #     if sock is self.listener_socket:
                #         self.accept_new_connection()
                #     elif sock is self.web_server_socket:
                #         # Accept a connection from the LOCAL web server
                #         self.accept_new_connection(sock, source='web') # Pass source/flag
                #     else: 
                #         self.handle_readable_client(sock) # existing client connection
                
                # for sock in writable:
                    # Handle sending queued data
                    # pass

                
                for sock in exceptional:
                    logger.warning(f"Handling exceptional condition for socket {sock.fileno()}")
                    addr = sock.getpeername() if sock.fileno() in self.client_sockets else "unknown"
                    self.cleanup_socket(sock, addr)

            except select.error as e:                
                logger.error(f"Select error: {e}")                
                if not self.stop_event.is_set():
                   time.sleep(0.1) # Avoid tight loop on persistent select errors
            except Exception as e:
                 # Catch other unexpected errors in the loop
                 if self.stop_event.is_set():
                      break # Exit loop cleanly if stopping
                 logger.error(f"Error in server loop: {e}", exc_info=True)


        logger.info("Server select loop finished.")
        self.cleanup_all_sockets() # Clean remaining sockets after loop exits

    # def accept_new_connection(self, source:str =""):
    #     """Accept a new connection from the listener socket."""
    #     try:
    #         client_socket, addr = self.listener_socket.accept()
    #         client_socket.setblocking(False)
    #         self.inputs.append(client_socket)        
    #         self.client_sockets[client_socket.fileno()] = client_socket
    #     except BlockingIOError:
    #         # This can happen if the listener is non-blocking and no connection is actually ready
    #         pass
    #     except Exception as e:
    #         logger.error(f"Error accepting new connection: {e}")
    def accept_new_connection(self, listener_sock: socket.socket, source: str = "unknown"):
        """Accept a new connection from the SPECIFIED listener socket."""
        try:            
            client_socket, addr = listener_sock.accept()
            # logger.info(f"Accepted connection from {addr} via '{source}' listener ({listener_sock.getsockname()})")

            client_socket.setblocking(False)
            self.inputs.append(client_socket)
            # Store the client socket. You might want to know its source later
            # e.g., self.client_sockets[client_socket.fileno()] = {'socket': client_socket, 'source': source}
            # or just store the socket if you check the source IP in the handler
            self.client_sockets[client_socket.fileno()] = client_socket

        except BlockingIOError:
            # Expected for non-blocking sockets if readiness was spurious
            pass
        except Exception as e:
            # Log which listener failed
            listener_name = listener_sock.getsockname() if listener_sock else 'unknown listener'
            logger.error(f"Error accepting new connection ({source}) on {listener_name}: {e}", exc_info=True)

    def handle_readable_client(self, sock: socket.socket):
        """Handle data received on a client socket."""
        addr = "unknown"
        try:
            addr = sock.getpeername()            
            data = sock.recv(4096)

            if data:                
                self.client_executor.submit(self._process_received_data, data, sock, addr)
            else:                
                self.cleanup_socket(sock, addr)

        except BlockingIOError:            
            pass
        except ConnectionResetError:
            logger.warning(f"Client {addr} forcibly closed the connection.")
            self.cleanup_socket(sock, addr)
        except socket.error as e:
            logger.error(f"Socket error reading from {addr}: {e}")
            self.cleanup_socket(sock, addr)
        except Exception as e:
            logger.error(f"Error handling readable client {addr}: {e}")
            self.cleanup_socket(sock, addr) # Clean up on unexpected errors


    def _process_received_data(self, data: bytes, client_socket: socket.socket, addr: tuple):
        """Worker function (runs in thread pool) to decode and process message."""
        try:
            msg_obj = json.loads(data.decode('utf-8'))
            # Call the original processing logic
            self.process_message(msg_obj, client_socket, addr)
        except json.JSONDecodeError as json_d:
            logger.error(f"Invalid JSON received from {addr}: {json_d} - Data: {data[:25]}...")
        except Exception as e:
            logger.error(f"Error processing message from {addr} in worker thread: {e}", exc_info=True)
        

    # ========================================================================
    # Outgoing Request Handling (_handle_file_request) - Kept Threaded
    # This part handles *initiating* requests, separate from the select loop
    # for *incoming* connections. Using threads here is simpler than
    # integrating complex non-blocking connect/send/recv state into select.
    # ========================================================================

    def req_file(self, host: str, port: int, file_id):
        """Spawns a thread to handle an outgoing file request."""
        # This remains unchanged - uses standard threading for outgoing requests
        thread = threading.Thread(target=self._handle_file_request, args=(host, port, file_id))
        thread.daemon = True # Prevent these threads from blocking shutdown
        thread.start()

    def _handle_file_request(self, host: str, port: int, file_id):
        """Handles a single outgoing file request and processes the response."""

        s = None
        try:

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(10.0)
                s.connect((host, port))
                request_message = {
                    "type": "GET_FILE",
                    "file_id": file_id
                }
                request_bytes = json.dumps(request_message).encode('utf-8')
                s.sendall(request_bytes)
                logger.info(f"Sent GET_FILE request for {file_id} to {host}:{port}")
                
                response_data = b""
                while True: 
                     chunk = s.recv(4096)
                     if not chunk:
                          break
                     response_data += chunk
                     
                     if response_data.strip().endswith(b'}'):
                          break

                if response_data:
                    response_obj = json.loads(response_data.decode('utf-8'))
                    logger.info(f"Received response for GET_FILE({file_id}) from {host}:{port}")        
                    self.process_message(response_obj, None, (host, port))
                else:
                    logger.warning(f"No response received for GET_FILE({file_id}) from {host}:{port}")

        except socket.timeout:
            logger.warning(f"Timeout during GET_FILE request/response for {file_id} to {host}:{port}")
        except socket.error as e:
            logger.error(f"Socket error in _handle_file_request for {file_id} to {host}:{port}: {e}")
        except json.JSONDecodeError as e:
             logger.error(f"Failed to decode JSON response for {file_id} from {host}:{port}: {e} - Data: {response_data[:100]}...")
        except Exception as e:
            logger.exception(f"Unexpected error in _handle_file_request for {file_id}: {e}")
        


    # ========================================================================
    # Message Processing and Sending Logic
    # ========================================================================

    def process_message(self, msg_obj: dict, client_socket: socket.socket | None, addr: tuple):
        """Process incoming messages based on their type.
           client_socket can be None if called from _handle_file_request response.
        """
        msg_type = msg_obj.get("type")

        if msg_type == "GOSSIP":
            origin_host = msg_obj.get("host")
            origin_port = int(msg_obj.get("port")) 
            origin_peerId = msg_obj.get("peerId")
            gossip_id = msg_obj.get("id")

            if all([origin_host, origin_port, origin_peerId, gossip_id]) and origin_peerId != self.args.um_id:
                if not self.network_tracker.id_exists(gossip_id):
                    self.network_tracker.save_id(gossip_id)
                    self.network_tracker.update_peers(origin_peerId, (origin_host, origin_port))
                    self.send_gossip_reply(origin_host, origin_port, gossip_id)
                    logger.info(f"Got a GOSSIP from {origin_host}:{origin_port}")
                # else:
                    # logger.debug(f"Ignoring duplicate GOSSIP ID {gossip_id} from {addr}")


        elif msg_type == "GOSSIP_REPLY":
            g_host, g_port, g_peer_id, files = msg_obj.get("host"), int(msg_obj.get("port")), msg_obj.get("peerId"), msg_obj.get("files")

            if all([g_host, g_port, g_peer_id, files is not None]):
                
                f_to_req = self.db.files_to_get(files)
                logger.info(f"{g_peer_id} with files : {files} ")
                self.db.files_to_users(g_peer_id, files)
                logger.info(f"Received GOSSIP_REPLY from {addr}, need {len(f_to_req) if f_to_req is not None else ''} files.")
                if f_to_req:
                     logger.debug(f"Requesting files: {f_to_req}")
                for f_id in f_to_req:
                    self.req_file(g_host, g_port, f_id) # Initiates outgoing requests

        elif msg_type == "GET_FILE":                        
            f_id = msg_obj.get("file_id")
            if f_id:
                logger.info(f"Processing GET_FILE request for {f_id} from {addr}")
                f_data = self.db.get_file_data(f_id)
                if f_data:

                    self.send_file_data(f_data, client_socket)
                    logger.info(f"SUCCESS: Sent data for file: {self.db.file_ids.get(f_id)} to {addr}")
                    
                else:
                    logger.warning(f"File data not found for requested id: {f_id} from {addr}")
            else:
                 logger.warning(f"Received GET_FILE request without file_id from {addr}")

        elif msg_type == "FILE_DATA":    
            try:
                  f_name = msg_obj["file_name"]
                  f_size = msg_obj["file_size"]
                  f_id = msg_obj["file_id"]
                  f_owner = msg_obj["file_owner"]
                  f_tstmp = msg_obj["file_timestamp"]
                  f_contnt = msg_obj["data"] 

                  logger.info(f"Received FILE_DATA for '{f_name}' ({f_id}) from {addr}")

                  if f_name and f_size and  f_id and f_owner and f_tstmp and  f_contnt:
                      self.db.save_new_file(f_name, f_size, f_id, f_owner, f_tstmp, f_contnt) 
                    #   self.send_announcement()
                      logger.info(f"Successfully saved file: {f_name}")
                  else:
                      logger.error(f"Incomplete FILE_DATA received from {addr}: Missing fields.")        

            except KeyError as e:
                logger.error(f"Missing key {e} in FILE_DATA received from {addr}: {msg_obj}")
            except Exception as e:
                logger.error(f"Error processing received FILE_DATA from {addr}: {e}", exc_info=True)


        elif msg_type == "ANNOUNCE":                        
            acc = msg_obj["from"]            
            f_id = msg_obj["file_id"]            
            f_name = msg_obj["file_name"]            
            db_fname = self.db.file_ids.get(f_id)
            
            if f_id in self.db.db and f_name == db_fname: 
                # self.network_tracker.save_announcement(f_id, acc)
                logger.info(f"{msg_type}: Stored {acc} has file {f_name}") 

        elif msg_type == "DELETE":
            logger.info(f"{msg_type} received from {addr}: {msg_obj}")
            # TODO: Implement DELETE logic
            
        elif msg_type == "WEB_LIST":            
            original_list = self.db.db
            augmented_list = []
            for file_data in original_list:
                new_file_data = file_data.copy() 
                f_name = new_file_data.get("file_name")
                peers = self.db.get_peer_with_file(f_name)
                new_file_data["peer_w_file"] = peers 
                augmented_list.append(new_file_data)
                         
            response_msg = {"status": "SUCCESS", "request_type": "LIST", "message": augmented_list } if augmented_list else {"status": "ERROR", "request_type": "LIST", "message": "UNSUCCESSFULL" }                                          
            self.send_ws_response(response_msg, client_socket)
            logger.info(f"WEB_LIST sends : {response_msg}")                        
        elif msg_type == "WEB_GET_PEERS":
            peer_status = self.network_tracker.get_peers_status()  
            logger.info(f"Peer status: {peer_status}")                        
            response_msg = {"status": "SUCCESS", "request_type": "LIST", "message": peer_status } if peer_status else {"status": "ERROR", "request_type": "LIST", "message": "Couldn't fetch peer status" }                                          
            self.send_ws_response(response_msg, client_socket)
            logger.info(f"WEB_LIST sends : {response_msg}")                        
        else:
            logger.warning(f"Received unknown message type '{msg_type}' from {addr}")
            
            
    def send_ws_response(self, response: dict , ws_sock: socket.socket ):
        try:
            reply_message  = json.dumps(response).encode("utf-8")
            ws_sock.sendall(reply_message)
            logger.info(f"Sent reply to web server: {reply_message}") #TODO: convert to debug
        except socket.error as e:
            logger.error(f"Socket error sending reply to web server {ws_sock.getpeername()}: {e}")
            self.cleanup_socket(ws_sock, "web server send error")
        except Exception as e:
            logger.error(f"Error processing web server command or sending reply: {e}", exc_info=True)
            # Ensure cleanup happens even on other errors
            self.cleanup_socket(ws_sock, "web server processing error")
                
        
    
    
    def send_announcement(self, f_name: str, f_size: str, f_id: str , f_owner: str, f_timestamp: str) -> None: 
        # {
        #    "type": "ANNOUNCE",
        #    "from": "Peer ID",
        #    "file_name": "File name",
        #    "file_size": 123,
        #    "file_id": "Hash of the content + timestamp",
        #    "file_owner": "Owner ID",
        #    "file_timestamp": 123456,
        # }
        message = {
           "type": "ANNOUNCE",
           "from": f_owner,
           "file_name": f_name,
           "file_size": f_size,
           "file_id": f_id,
           "file_owner": f_owner,
           "file_timestamp": f_timestamp,
        }
        pass
    
    def send_file_data(self, content: dict, c_socket: socket.socket) -> None:
        """Send generic data (intended for FILE_DATA) on an existing connection."""
        if not c_socket:
             logger.error("Attempted send_file_data with no socket.")
             return
        try:
            
            content.setdefault("type", "FILE_DATA")
            message_bytes = json.dumps(content).encode('utf-8')            
            c_socket.sendall(message_bytes)
        except socket.error as e:
            logger.error(f"Socket error sending data to {c_socket.getpeername()}: {e}")            
        except Exception as e:
            logger.exception(f"Unexpected error sending data: {e}")

    def send_gossip_reply(self, host, port, gossip_id):
        """Send a GOSSIP_REPLY by creating a new connection."""        
        reply_socket = None
        try:
            reply_socket = socket.create_connection((host, port), timeout=5.0)
            reply_message = {
                "type": "GOSSIP_REPLY",
                "host": self.args.host if self.args.host else socket.gethostbyname(socket.gethostname()),
                "port": self.args.port,
                "peerId": self.args.um_id,
                "files": self.db.db 
            }
            message_bytes = json.dumps(reply_message).encode('utf-8')
            reply_socket.sendall(message_bytes)
            # logger.info(f"Sent GOSSIP_REPLY regarding {gossip_id} to {host}:{port}")
        except socket.gaierror:
            logger.error(f"Failed GOSSIP_REPLY to {host}:{port}: Hostname lookup failed.")
        except socket.timeout:
            logger.error(f"Timeout connecting for GOSSIP_REPLY to {host}:{port}.")
        except socket.error as e:
            logger.error(f"Socket error sending GOSSIP_REPLY to {host}:{port}: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error sending GOSSIP_REPLY to {host}:{port}: {e}")
        finally:
            if reply_socket:
                reply_socket.close()

    def send_initial_gossip(self):                
        try:
            well_known = self.network_tracker.get_bootstrap() if getattr(self.args,'environment', 'DEV') == "PROD" else ["127.0.0.1: 8999"]
            for peer in well_known: 
                boot_addr, boot_port = peer.split(":")
                logger.info(f"Sending initial gossip to bootstrap node {boot_addr}:{boot_port}")        
                self.send_gossip(boot_addr, int(boot_port))
            
        except Exception as e:
            logger.error(f"Failed to get bootstrap node: {e}")
            return



    def send_gossip(self, host: str, port: int) -> None:
        """Send a GOSSIP message via TCP by creating a new connection."""        
        gossip_socket = None
        try:
            gossip_socket = socket.create_connection((host, port), timeout=5.0)
            gossip_message = {
                "type": "GOSSIP",
                "host": self.args.host if self.args.host else socket.gethostbyname(socket.gethostname()),
                "port": self.args.port,
                "id": str(uuid.uuid4()),
                "peerId": self.args.um_id
            }
            message_bytes = json.dumps(gossip_message).encode('utf-8')
            gossip_socket.sendall(message_bytes)
            logger.debug(f"Sent GOSSIP message {gossip_message['id']} to {host}:{port}")
        except socket.gaierror:
            logger.error(f"Failed GOSSIP to {host}:{port}: Hostname lookup failed.")
        except socket.timeout:
             logger.error(f"Timeout connecting for GOSSIP to {host}:{port}.")
        except socket.error as e:
            logger.error(f"Socket error sending GOSSIP to {host}:{port}: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error sending GOSSIP to {host}:{port}: {e}")
        finally:
            if gossip_socket:
                gossip_socket.close()

    # ========================================================================
    # Shutdown Logic
    # ========================================================================

    def cleanup_all_sockets(self):
         """Close listener and all active client sockets."""
         logger.info("Cleaning up all network sockets...")
         # Close listener first
         if self.listener_socket:
              self.cleanup_socket(self.listener_socket, "listener")
              self.listener_socket = None
         
         client_sockets_copy = list(self.client_sockets.values())
         for sock in client_sockets_copy:
             try:
                  addr = sock.getpeername()
             except OSError:
                  addr = "already closed?"
             self.cleanup_socket(sock, addr)
         self.client_sockets.clear()
         self.inputs.clear()
         self.outputs.clear()
         logger.info("Finished cleaning up sockets.")


    def shutdown(self):
        """Gracefully shut down the peer protocol."""
        if not self.running:
            return
        logger.info("Initiating shutdown sequence...")
        self.running = False
        self.stop_event.set()
        self.cleanup_all_sockets()
        logger.info("Shutting down message processing thread pool...")
        self.client_executor.shutdown(wait=False, cancel_futures=False) 
        logger.info("Message processing thread pool shut down.")        
        logger.info("Peer protocol shutdown complete.")
