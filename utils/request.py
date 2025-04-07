from dataclasses import dataclass
from enum import Enum

from utils.logger import Logger, LoggerClass

logger: LoggerClass = Logger(__name__).get_logger()

__all__ = ["Request"]
__author__ = "Saksham Bedi"


class RequestType(Enum):
    LOGIN = "LOGIN"
    PUSH = "PUSH"
    LIST = "LIST"
    GET = "GET"
    DELETE = "DELETE"
    CD = "CD"
    LS = "LS"
    ERROR = "ERROR"
    DATA = "DATA"
    IGNORE = "IGNORE"

    def __str__(self) -> str:
        return self.value


@dataclass
class Request:
    type: RequestType
    args: list[str]
    error: str | None = None

    @classmethod
    def parse(cls, data: str) -> "Request":
        try:
            input_req = data.strip()
            parts = input_req.split()
            try:
                req_type = RequestType(parts[0].upper())
            except ValueError:
                return cls(RequestType.ERROR, [], f"Unknown request type: '{parts[0]}'")

            if not parts:
                logger.error("Empty request after splitting")
                return cls(RequestType.ERROR, [], "Empty request")
            args = parts[1:] if len(parts) > 1 else []

            return cls(req_type, args)

        except Exception:
            return cls(
                RequestType.ERROR, [], "An error occurred while parsing the request"
            )

    @staticmethod
    def _validate_args(req_type: RequestType, args: list[str]) -> str | None:
        arg_requirements = {
            RequestType.LOGIN: 1,
            RequestType.PUSH: 2,
            RequestType.GET: 1,
            RequestType.DELETE: 1,
            RequestType.LIST: 0,
            RequestType.DATA: 1,
        }

        if req_type in arg_requirements and len(args) != arg_requirements[req_type]:
            return f"Invalid number of arguments for {req_type.name}.\nExpected {arg_requirements[req_type]}, got {len(args)}"
        return None
