import base64
import json
import os
import select
import socket
import threading
import uuid
from queue import Queue

from utils import misc
from utils.logger import Logger, LoggerClass
from utils.misc import http_responses, valid_api_req
from utils.reponse import Response, ResponseStatus

logger: LoggerClass = Logger(__name__).get_logger()


class webserver_protocol:
    def __init__(self, args) -> None:
        assert len(str(args.port)) >= 4, ""
        logger.info(f"Web Server initializing with args: {args}")
        self.args = args # Store args if needed elsewhere
        self._socket = self.setup_socket(args.web_host, args.web_port)

        # --- Remove File Server Specifics ---
        # self._fs_socket = self.connect_to_file_server(args.fs_host, args.fs_port)
        # self.fs_lock = threading.Lock()
        # self.fs_response_queue = Queue()
        # ------------------------------------

        # --- Store reference to P2P Protocol ---        
        # ---------------------------------------

        self.index_path = os.path.join(os.getcwd(), "ui", "index.html")
        self.error404_path = os.path.join(os.getcwd(), "ui", "404.html")
        self.user_ids: set = set() # For session cookies
        self.logged_users: dict[str, str] = {} # {session_cookie: user_peer_id} - Map cookie to P2P ID
        
        # -- old --
        # self._socket = self.setup_socket(args.host, args.port)
        # self._fs_socket = self.connect_to_file_server(args.fs_host, args.fs_port)
        # self.fs_lock = threading.Lock()
        # self.fs_response_queue = Queue()

        # self.index = open(os.path.join(os.getcwd(), "ui", "index.html")).read()
        # self.error404 = open(os.path.join(os.getcwd(), "ui", "404.html")).read()
        # self.user_ids: set = set()
        # self.logged_users: dict[str, str] = {}
        # self.buffer: dict[str, list] = {}

    def setup_socket(self, host: str, port: int) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen()
        sock.setblocking(True)

        logger.info(
            f"socket is accepting connections on {host if host != '' else 'localhost'}@{port}"
        )
        return sock

    def connect_to_file_server(self, fs_addr: str, fs_port: int) -> socket.socket:
        fs_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        fs_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            fs_socket.connect((fs_addr, fs_port))
            logger.info(f"Connected to file server at {fs_addr}:{fs_port}")
        except ConnectionRefusedError:
            logger.error(f"Connection to file server at {fs_addr}:{fs_port} refused")
            raise
        return fs_socket

    def send_fs_command(self, command: str) -> "Response":
        # A helper that sends a command over the persistent file server connection.
        with self.fs_lock:
            try:
                logger.info(f"Sending command to file server: {command.strip()}")
                self._fs_socket.sendall(command.encode("utf-8"))
                response = self._fs_socket.recv(4096).decode("utf-8")
                if response is not None:
                    response = Response.from_json(response)
                    logger.info(f"Received response: {response}")
                return response
            except Exception as e:
                logger.error("Error in communication with file server: " + str(e))
                raise

    def run(self) -> None:
        try:
            while True:
                readable, writable, _ = select.select([self._socket], [], [])
                if self._socket in readable:
                    client_socket, client_address = self._socket.accept()
                    client_thread = threading.Thread(
                        target=self.handle_client, args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                if self._socket in writable:
                    pass
        except KeyboardInterrupt:
            raise
        finally:
            self._socket.close()

    def recv_all(self, socket, n):
        # Helper to ensure exactly n bytes are read
        data = b""
        while len(data) < n:
            packet = socket.recv(n - len(data))
            if not packet:
                break
            data += packet
        return data

    def handle_client(self, client_socket, client_address):
        print(f"Connected to {client_address}")
        try:
            # Read until the end of headers
            buffer = b""
            while b"\r\n\r\n" not in buffer:
                buffer += client_socket.recv(1024)

            header_data, remaining = buffer.split(b"\r\n\r\n", 1)
            header_text = header_data.decode("utf-8")
            headers = misc.parse_headers(
                header_text
            )  # your function to parse headers into a dict
            parts = header_text.splitlines()[0].split(" ")  # Request-Line
            if len(parts) < 3:
                logger.error("Malformed request line")
                response = http_responses.error400("Bad Request")
                client_socket.sendall(response.encode("utf-8"))
                return
            method, path, _ = parts
            c_ip, c_port = client_address
            uaddr_uuid = f"{c_ip}:{c_port}"
            api = [route for route in path.split("/") if route != ""]

            # Determine the length of the body, if any
            content_length = int(headers.get("Content-Length", "0"))

            # For endpoints that receive binary data
            if headers.get("Content-Type", "").lower() == "application/octet-stream":
                body_bytes = remaining
                if len(body_bytes) < content_length:
                    body_bytes += self.recv_all(
                        client_socket, content_length - len(body_bytes)
                    )
                data = body_bytes  # binary data; DO NOT decode!
            else:
                # Assume the remainder is text and decode as UTF-8.
                if remaining:
                    body_text = remaining.decode("utf-8")
                else:
                    body_text = ""
                # If more body is expected, read and decode.
                if len(body_text) < content_length:
                    body_text += client_socket.recv(
                        content_length - len(body_text)
                    ).decode("utf-8")
                data = body_text
            encode = True
            # Process routing and API endpoints
            if path == "/":
                response = http_responses.success200(self.index)
            elif path == "/stats":
                response = http_responses.success200(self.index)
            elif api[1:] and api[0] == "api":
                if not valid_api_req(method, api[1:], data):
                    logger.error(f"Invalid API request for {'/'.join(api)}")
                    response = http_responses.error400("Invalid API request.")
                else:
                    if api[1] != "upload":
                        # For non-upload endpoints assume JSON text
                        data = json.loads(data) if data else {}
                    response, encode = self.handle_api_req(
                        headers, method, api[1:], data, uaddr_uuid
                    )
            else:
                logger.info(f"Client requested {path}")
                response = http_responses.error404(self.error404)

            client_socket.sendall(response.encode("utf-8") if encode else response)
        except Exception as ex:
            print(f"Error handling client {client_address}: {ex}")
        finally:
            client_socket.close()
            print(f"Closed connection to {client_address}")

    def generate_cookie(self):
        new_id = str(uuid.uuid4())
        while new_id in self.user_ids:
            new_id = str(uuid.uuid4())
        self.user_ids.add(new_id)
        return new_id

    def handle_api_req(
        self,
        header: dict,
        method: str,
        api_path: list[str],
        body: dict,
        uaddr_uuid: str,
    ) -> tuple[str, bool]:
        pth = api_path[0]
        if pth == "login":
            u_name = body["username"]
            if method == "POST":
                # now we send the login request to the file server and add that to the list of user.
                resp = self.send_fs_command(f"LOGIN {u_name} {uaddr_uuid}")
                if resp.status == ResponseStatus.ERROR:
                    return http_responses.error400("LOGIN UNSUCESSFULL"), True

                cookie = self.generate_cookie()
                self.logged_users.setdefault(cookie, uaddr_uuid)

                return http_responses.success200("LOGIN SUCCESSFULL", cookie), True
            else:
                # uname will be used to delete the user from the fm_server
                _, user_cookie = header["Cookie"].split("=")
                del self.logged_users[user_cookie]
                self.user_ids.remove(user_cookie)
                return http_responses.success200("LOGOUT SUCCESSFULL"), True

        elif pth == "session-status":
            user_cookie = header["Cookie"].removeprefix("session_id=")
            logg_status = (
                True
                if user_cookie and user_cookie in self.logged_users.keys()
                else False
            )
            message = misc.json_body("loggedIn", logg_status)
            return http_responses.success200(message), True
        elif pth == "list":
            resp = self.send_fs_command("LIST")
            if resp.status == ResponseStatus.ERROR:
                return http_responses.error400("Refresh failed!"), True

            l_elem = list(json.loads(resp.message).values())[-1]
            # logger.info(f"LIST({type(l_elem)}): {l_elem}")
            return http_responses.success200(f"{l_elem}"), True
        elif pth == "upload":
            user_cookie = header.get("Cookie", None)
            if user_cookie is None:
                return http_responses.unauthorizedaccess401(b"No cookie present"), False
            user_cookie = user_cookie.removeprefix("session_id=")

            logger.info(f"USER cookie for upload  : {user_cookie} ")
            f_owner = self.logged_users.get(user_cookie)
            f_name = header["X-File-Name"]

            logger.info(f"Saving file to the fileserver : {f_name} from {f_owner}")

            res = self.store_to_FileS(
                file_name=f_name, content=body, uaddr_uuid=f_owner
            )
            if res.status == ResponseStatus.ERROR:
                return http_responses.error400(res.message), True
            return http_responses.success200(res.message), True

        elif pth == "download":
            f_name = header["X-File-Name"]

            logger.info(f"Got req : {pth} : {f_name}")

            file_bin = self.download_file(f_name)
            if not file_bin:
                return http_responses.error400(
                    f"Download failed for file  : {f_name}!"
                ), True

            return http_responses.success200filedownload(file_bin), False

        elif pth.startswith("delete?file="):
            _, file = pth.split("?")
            if not file.startswith("file="):
                return http_responses.error400(
                    f"Request missing the file name argument. Got : {pth}!"
                ), True

            _, f_name = file.split("=")
            _, user = header["Cookie"].split("=")
            delete_u_req = self.logged_users[user]

            logger.info(
                f"Request submitted by: '{delete_u_req}' to delete file: {f_name} "
            )

            # Send the delete message to the server
            resp = self.send_fs_command(f"DELETE {f_name}|{delete_u_req}")

            if resp.status == ResponseStatus.ERROR:
                return http_responses.error400(resp.message), True
            return http_responses.success200(), True

        else:
            return http_responses.error400(
                "WEBserver doesnt know how to respond to this request!"
            ), True

    def download_file(self, file_name: str) -> str:
        _buff = ""
        self._fs_socket.sendall(f"GET {file_name}".encode("utf-8"))

        getting_file = True

        while getting_file:
            data = self._fs_socket.recv(4096).decode("utf-8").split("\n")
            data = data[:-1] if data[-1] == "" else data

            for incom_data in data:
                line = incom_data.split(" ", 1)[-1]
                logger.info(f"incoming data : {line}")
                if line != "END":
                    _buff += line
                else:
                    return base64.b64decode(_buff)

    def store_to_FileS(self, file_name: str, content: bytes, uaddr_uuid: str):
        file_content = base64.b64encode(content)
        filesize = len(file_content)
        bytes_sent = 0

        res = self.send_fs_command(f"PUSH {file_name} {filesize} {uaddr_uuid}\n")
        if res.status == ResponseStatus.ERROR:
            print(f"Server Denied Request to push the file : {file_name} to the server")
            return res

        while bytes_sent < filesize:
            remaining = filesize - bytes_sent

            chunk = file_content[bytes_sent : bytes_sent + min(4090, remaining)]

            if not chunk:
                break

            header = b"DATA " + chunk + b"\n"
            self._fs_socket.sendall(header)
            bytes_sent += len(chunk)

        res = self.send_fs_command("DATA END")

        return res
