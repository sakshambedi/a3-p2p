import json
from dataclasses import dataclass
from enum import Enum

from utils.request import RequestType


class ResponseStatus(Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"

    def __str__(self) -> str:
        return self.value


@dataclass
class Response:
    status: ResponseStatus
    request_type: RequestType
    message: str

    def to_json(self):
        data = {
            "status": self.status.value,
            "request_type": self.request_type.value,
            "message": self.message,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str):
        # Method to deserialize JSON back to Response object
        data = json.loads(json_str)

        return cls(
            status=ResponseStatus(data["status"]),
            request_type=RequestType(data["request_type"]),
            message=data["message"],
        )

    def __str__(self):
        if self.message:
            mes = self.message
        return f"REQ:{self.request_type}, STATUS: {self.status}, MESSAGE({type(mes)}) : {mes}"
