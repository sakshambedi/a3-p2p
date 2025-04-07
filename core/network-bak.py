import argparse
import json
import socket
import threading
import uuid
import concurrent.futures 

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
        self.listener_socket = None
        self.listener_thread = None        
        
        # Use a fixed-size thread pool to prevent resource exhaustion from too many connections
        self.client_executor = concurrent.futures.ThreadPoolExecutor(
            # Consider making max_workers configurable via args
            max_workers=getattr(args, 'max_connections', 50),
            thread_name_prefix='ClientHandler'
        )
        self.__start()

    def __start(self) -> None:
        try:
            self.start_sockets()
            self.send_initial_gossip()
        except Exception as e:
            logger.error(f"Failed to start peer protocol: {e}")
            self.shutdown() # Attempt cleanup if start fails
            raise

    def start_sockets(self):
        """Initialize and start listening on TCP socket."""
        host = self.args.host
        port = self.args.port
        logger.info(f"Attempting to bind socket to {host}:{port}")

        try:
            self.listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.listener_socket.bind((host, port))
            self.listener_socket.listen()            
            # self.listener_socket.settimeout()
            self.listener_thread = threading.Thread(
                target=self.listen_for_connections,
                name="TCPListener"
            )
            self.listener_thread.start()
            logger.info(f"TCP Listener started on {host}:{port}")
        except Exception as e:
            logger.error(f"Failed to start TCP listener: {e}")
            self.cleanup_socket()
            raise

    def cleanup_socket(self):
        """Safely close the listener socket."""
        if self.listener_socket:
            try:
                self.listener_socket.close()
            except Exception as e:
                logger.error(f"Error closing listener socket: {e}")
            self.listener_socket = None
            logger.info("Listener socket closed.")


    def listen_for_connections(self) -> None:
        """Listen for incoming TCP connections and submit them to the thread pool."""
        while not self.stop_event.is_set():
            try:
                client_socket, addr = self.listener_socket.accept()
                # logger.debug(f"Accepted connection from {addr}")
                # Submit the handling task to the thread pool instead of creating a new thread directly
                self.client_executor.submit(self.handle_client, client_socket, addr)

            except socket.timeout:                
                continue
            except OSError as e:
                if self.stop_event.is_set():
                    # Expected error when socket is closed during shutdown
                    logger.info("Listener socket closed, shutting down listener loop.")
                    break
               
                logger.error(f"Socket error while listening: {e}")
                
                break # Example: break on significant errors
            except Exception as e:
                if self.stop_event.is_set():
                    break # Exit loop if shutdown is requested
                logger.error(f"Error accepting connection: {e}")
                

        logger.info("Listener thread finished.")

    def handle_client(self, client_socket : socket.socket , addr):
        """Handles a single client connection (runs in a thread pool thread)."""
        try:
            # Consider a receive timeout on the client socket
            # client_socket.settimeout(30.0)
            data = client_socket.recv(4096) # Use a reasonable buffer size
            if not data:            
                return
            msg_obj = json.loads(data.decode('utf-8'))
            self.process_message(msg_obj, client_socket, addr)

        except json.JSONDecodeError as json_d:
            logger.error(f"Invalid JSON received from {addr}: {json_d}")        
        except ConnectionResetError:
             logger.warning(f"Client {addr} reset the connection.")
        except Exception as e:            
            logger.error(f"Error handling client {addr}: {e}")
        finally:            
            try:
                
                client_socket.shutdown(socket.SHUT_RDWR)
            except (OSError, socket.error):
                 
                 pass
            finally:
                client_socket.close()
    
    
    def req_file(self, host: str, port: int, file_id):
    # Spawn a new thread to handle the file request asynchronously.
        thread = threading.Thread(target=self._handle_file_request, args=(host, port, file_id))
        thread.daemon = True  # Mark thread as daemon so it doesn't block program exit
        thread.start()


    def _handle_file_request(self, host: str, port: int, file_id):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, port))
                message = {
                    "type": "GET_FILE",
                    "file_id": file_id
                }
                message_bytes = json.dumps(message).encode('utf-8')
                s.sendall(message_bytes)
                logger.info(f"Sent GET_FILE request for file_id {file_id} to {host}:{port}")

                # Optionally set a timeout to avoid blocking indefinitely
                s.settimeout(30.0)
                response = s.recv(4096).decode('utf-8')
                if response:
                    try:
                        response = json.loads(response)            
                        # Process the response (expected to be FILE_DATA)                    
                        msg_type = response.get("type")
                        if msg_type == "FILE_DATA":
                
                            f_name, f_size, f_id, f_owner, f_tstmp, f_contnt = (
                                response["file_name"],
                                response["file_size"],
                                response["file_id"],
                                response["file_owner"],
                                response["file_timestamp"],
                                response["data"],
                            )
                            logger.info(f"GOT a Req for FILE_DATA: {f_name}")
                            if all([ f_name, f_size, f_id, f_owner, f_tstmp, f_contnt]) :                
                                self.db.save_new_file(f_name, f_size, f_id, f_owner, f_tstmp, f_contnt)                 
                            logger.info(f"Received FILE_DATA from {host}/{port} : {f_name}")
                    except JSONDecodeError :
                        logger.warning(f"JSON Decode error for :{message}")
                # else:
                #     logger.warning(f"No response received for file_id {file_id} from {host}:{port}")
        except socket.timeout:
            logger.warning(f"Timeout waiting for response for file_id {file_id} from {host}:{port}")
        except socket.error as e:
            logger.error(f"Socket error in _handle_file_request for {host}:{port} with file_id {file_id}: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error in _handle_file_request: {e}")
        

    def process_message(self, msg_obj: dict, client_socket: socket.socket, addr: tuple):
        """Process incoming messages based on their type."""
        msg_type = msg_obj.get("type")
        if msg_type == "GOSSIP":
            origin_host = msg_obj.get("host")
            origin_port = msg_obj.get("port")
            origin_peerId = msg_obj.get("peerId")
            gossip_id = msg_obj.get("id")

            if all([origin_host, origin_port, origin_peerId, gossip_id]) and origin_peerId != self.args.um_id:
                if not self.network_tracker.id_exists(gossip_id):
                    logger.info(f"GOSSIP message received : {msg_obj}")
                    self.network_tracker.save_id(gossip_id)
                    self.network_tracker.update_peers(origin_peerId, addr)
                    self.send_gossip_reply(origin_host, origin_port, gossip_id)

        elif msg_type == "GOSSIP_REPLY":
            g_host, g_port, g_peer_id, files = msg_obj.get("host"), int(msg_obj.get("port")), msg_obj.get("peerId"), msg_obj.get("files")

            if all([g_host, g_port, g_peer_id, files]):                
                f_to_req = self.db.files_to_get(files)                                            
                for f_id in f_to_req:
                    self.req_file(g_host, g_port, f_id)

        elif msg_type == "GET_FILE":
            f_id = msg_obj.get("file_id")
            if f_id:
                f_data = self.db.get_file_data(f_id)
                if f_data:
                    self.send_file_data(f_data, client_socket)
                    logger.info(f"SUCCESS: Sent data for file: {self.db.file_ids.get(f_id, f_id)} to {addr}")
                else:
                    logger.warning(f"File data not found for requested id: {f_id} from {addr}")                    
            else:
                 logger.warning(f"Received GET_FILE request without file_id from {addr}")

        # elif msg_type == "FILE_DATA":
            
        #     f_name, f_size, f_id, f_owner, f_tstmp, f_contnt = (
        #         msg_obj["file_name"],
        #         msg_obj["file_size"],
        #         msg_obj["file_id"],
        #         msg_obj["file_owner"],
        #         msg_obj["file_timestamp"],
        #         msg_obj["data"],
        #     )
        #     logger.info(f"GOT a Req for FILE_DATA: {f_name}")
        #     if all([ f_name, f_size, f_id, f_owner, f_tstmp, f_contnt]) :                
        #         self.db.save_new_file(f_name, f_size, f_id, f_owner, f_tstmp, f_contnt)                 
        #     logger.info(f"Received FILE_DATA from {addr} : {f_name}")

        elif msg_type == "ANNOUNCE":
            logger.info(f"{msg_type} : {msg_obj}")
            # TODO: Implement ANNOUNCE logic

        elif msg_type == "DELETE":
            logger.info(f"{msg_type} : {msg_obj}")
            # TODO: Implement DELETE logic (ensure thread-safety if modifying shared state)

        else:
            logger.warning(f"Received unknown message type '{msg_type}' from {addr}")
            
    
    
    def accouncement(self, f_name, f_size, f_id, f_owner, f_tstmp, f_contnt, client_socket: socket.socket):
        pass


    def send_file_data(self, content: dict, c_socket: socket.socket) -> None:
        """Send file data back on the same connection it was requested on."""
        # This method is now called within handle_client, using the existing socket.
        try:
            message_bytes = json.dumps(content).encode('utf-8')
            c_socket.sendall(message_bytes)
        except socket.error as e:
            # Log error specific to this client connection
            logger.error(f"Socket error sending file data to client: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error sending file data to client: {e}")


    def send_gossip_reply(self, host, port, gossip_id):
        """Send a GOSSIP_REPLY to a peer that sent a GOSSIP message."""
        # Creates a new connection for the reply.
        reply_socket = None
        try:
            # Consider adding a timeout for the connection attempt
            reply_socket = socket.create_connection((host, port), timeout=5.0)

            reply_message = {
                "type": "GOSSIP_REPLY",
                "host": self.args.host if self.args.host else socket.gethostbyname(socket.gethostname()),
                "port": self.args.port,
                "peerId": self.args.um_id,
                "files": self.db.list_files()
            }

            message_bytes = json.dumps(reply_message).encode('utf-8')
            reply_socket.sendall(message_bytes)            

        except socket.gaierror:
            logger.error(f"Failed to send GOSSIP_REPLY to {host}:{port}: Hostname could not be resolved.")
        except socket.timeout:
            logger.error(f"Timeout connecting to {host}:{port} for GOSSIP_REPLY.")
        except socket.error as e:
            logger.error(f"Socket error sending GOSSIP_REPLY to {host}:{port}: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error sending GOSSIP_REPLY to {host}:{port}: {e}")
        finally:
            if reply_socket:
                reply_socket.close()


    def send_initial_gossip(self):
        """Send initial gossip message to a bootstrap node."""
        # Logic remains the same
        boot_addr, boot_port = self.network_tracker.get_bootstrap() if self.args.environment == "PROD" else ("127.0.0.1" , 8999) # Use 127.0.0.1 for local dev
        try:
            logger.info(f"Sending initial gossip to bootstrap node {boot_addr}:{boot_port}")
            self.send_gossip(boot_addr, boot_port)
        except Exception as e:            
            logger.warning(f"Failed to send initial gossip to {boot_addr}:{boot_port}: {e}")

    def send_gossip(self, host: str, port: int) -> None:
        """Send a GOSSIP message via TCP to the specified host and port."""        
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
            # logger.debug(f"Sent GOSSIP message to {host}:{port}")
            # logger.debug(f"Message: {gossip_message}")

        except socket.gaierror:
            logger.error(f"Failed to send GOSSIP to {host}:{port}: Hostname could not be resolved.")
        except socket.timeout:
             logger.error(f"Timeout connecting to {host}:{port} for GOSSIP.")
        except socket.error as e:
            logger.error(f"Socket error sending GOSSIP to {host}:{port}: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error sending GOSSIP to {host}:{port}: {e}")
        finally:
            if gossip_socket:
                gossip_socket.close()


    def shutdown(self):
        """Gracefully shut down the peer protocol."""
        if not self.running:
            return # Avoid shutting down multiple times
        logger.info("Initiating shutdown...")
        self.running = False

        self.stop_event.set()        

        logger.info("Shutting down client handler thread pool...")
        self.client_executor.shutdown(wait=True)
        logger.info("Client handler thread pool shut down.")
        
        self.cleanup_socket()         
        if self.listener_thread and self.listener_thread.is_alive():
            logger.info("Waiting for listener thread to join...")
            self.listener_thread.join()
            logger.info("Listener thread joined.")

    
        logger.info("Peer protocol shutdown complete.")