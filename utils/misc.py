import json
import hashlib
from utils.logger import Logger, LoggerClass

__all__ = ["api_response", "split_http"]

logger: LoggerClass = Logger(__name__).get_logger()


def file_hash(timestamp, file_content):
    hashBase = hashlib.sha256()
    hashBase.update(file_content)
    hashBase.update(str(timestamp).encode())
    file_id = hashBase.hexdigest()
    return file_id

def json_body(key, value):
    json_body = json.dumps({key: value})
    return json_body


def parse_headers(header_text) -> dict[str, str]:
    """
    Parse raw header text into a dictionary.
    """
    headers = {}
    lines = header_text.split("\r\n")
    for line in lines[1:]:  # Skip the Request-Line
        if ": " in line:
            key, value = line.split(": ", 1)
            headers[key] = value
    return headers


@DeprecationWarning
def split_http(req: str) -> tuple[dict, dict]:
    """Split the incoming http request into a header: dict and a body dict"""
    header_text, body_text = req.split("\r\n\r\n", 1)

    # body = json.loads(body_text) if body_text else {}
    body = body_text if body_text else {}
    logger.info(f"header : {header_text}\n{'--'*10 }\nbody : {body_text}")

    header_lines = header_text.split("\r\n")
    headers = {}
    if header_lines:
        headers["Request-Line"] = header_lines[0]
        for line in header_lines[1:]:
            if ": " in line:
                key, value = line.split(": ", 1)
                headers[key] = value
    return headers, body


def valid_api_req(method: str, req: list[str], body: dict) -> bool:
    if len(req) < 1:
        return False  # invalid

    p = req[0]
    if p == "login" and method == "POST" and len(body) > 0:
        return True
    elif p == "login" and method == "DELETE":        
        return True
    elif p == "peers" and method == "GET":
        return True
    elif p == "list" and method == "GET":
        return True
    elif p == "download" and method == "GET":
        return True
    elif p == "upload" and method == "POST":
        return True
    elif p.startswith("delete?file=") and method == "DELETE":
        return True
    elif p == "session-status" and method == "GET":
        return True
    else:
        return False  # any other endpoint or situation is considered invalid


class http_responses:
    @classmethod
    def error400(cls, message: str) -> str:
        """Return a 400 Bad Request HTTP response with a JSON message."""
        json_body = f'{{"message": "{message}"}}'

        content_length = len(json_body.encode("utf-8"))
        response = f"""HTTP/1.1 400 Bad Request\r
Content-Type: application/json\r
Content-Length: {content_length}\r
Connection: close\r
\r
{json_body}"""
        return response

    @classmethod
    def unauthorizedaccess401(cls, message: str) -> str:
        headers = [
            "HTTP/1.1 401 Unauthorized",
            f'WWW-Authenticate: Basic realm="{message}"',
        ]
        headers_str = "\r\n".join(headers) + "\r\n\r\n"
        response_bytes = headers_str.encode("utf-8")

        return response_bytes

    # f"""HTTP/1.1 401 Unauthorized WWW-Authenticate: Basic realm=\"{message}\""""

    @classmethod
    def success200filedownload(cls, content: bytes) -> bytes:
        # Start with the basic headers
        headers = [
            "HTTP/1.1 200 OK",
            "Content-Type: application/octet-stream",
            f"Content-Length: {len(content)}",
            "Connection: close",
        ]

        headers_str = "\r\n".join(headers) + "\r\n\r\n"
        response_bytes = headers_str.encode("utf-8") + content
        return response_bytes

    @classmethod
    def success200(cls, message="", cookie=None):
        con_l = len(message.encode("utf-8"))
        # Add the cookie header only if cookie is not None
        if cookie:
            response = f"""HTTP/1.1 200 OK\r
Content-Type: text/html\r
Content-Length: {con_l}\r
Set-Cookie: session_id={cookie}; Path=/; Max-Age=86400; HttpOnly; SameSite=Lax\r
Connection: close\r
\r
{message}"""
        else:
            response = f"""HTTP/1.1 200 OK\r
Content-Type: text/html\r
Content-Length: {con_l}\r
Connection: close\r
\r
{message}"""

        return response

    @classmethod
    def error404(cls, message, cookie=None):
        con_l = len(message.encode("utf-8"))
        # Add the cookie header only if cookie is not None
        if cookie:
            response = f"""HTTP/1.1 200 OK\r
Content-Type: text/html\r
Content-Length: {con_l}\r
Set-Cookie: session_id={cookie}; Path=/; Max-Age=86400; HttpOnly; SameSite=Lax\r
Connection: close\r
\r
{message}"""
        else:
            response = f"""HTTP/1.1 200 OK\r
Content-Type: text/html\r
Content-Length: {con_l}\r
Connection: close\r
\r
{message}"""

        return response


def api_response(path: str):
    response_body = f'{{"message": "You requested {path}"}}'
    r_length = len(response_body.encode("utf-8"))
    response = f"""HTTP/1.1 200 OK\r\n
Content-Type: application/json\r\n
Content-Length: {r_length}\r\n
\r\n
{response_body}"""
    return response
