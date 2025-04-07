from typing import Union
import os
from utils.logger import Logger, LoggerClass

logger: LoggerClass = Logger(__name__).get_logger()

class File_Manager:
    def __init__(self, server_data: str) -> None:
        self.data_dir = server_data

    def get_file(self, file_name: str) -> Union[None, bytes]:
        f_path = os.path.join(self.data_dir, file_name)
        
        f_content = None
        if os.path.isfile(f_path):
            with open(f_path, "rb") as f:
                file_content = f.read().hex()

        return file_content

    def delete_file(self, f_name: str) -> bool:
        f_path = os.path.join(self.data_dir, f_name)
        if os.path.isfile(f_path):
            os.remove(f_path)
            return True
        return False
    
    def save_file(self, file_name: str, content: str):
        cnt_b = bytes.fromhex(content)
        save_path = os.path.join(self.data_dir, file_name)
        with open(save_path, "wb") as file:
            file.write(cnt_b)
        logger.info(f"SUCCESS : saved {file_name} on the local disk")

