import json
import os
import hashlib

from core.file_manager import File_Manager
from utils.logger import Logger, LoggerClass

logger: LoggerClass = Logger(__name__).get_logger()


class DB_Manager:
    def __init__(self, db_file: str, server_data: str):
        self._data_dir: str = os.path.join(os.getcwd(), server_data)
        self.db_dir: str = os.path.join(os.getcwd(), db_file)
        self._db_data: None | dict = None
        self.fm: "File_Manager" = File_Manager(server_data)        
        self.file_ids: dict = {}  # store all the file IDs mapped to filenames

        self._connect_to_db()

    def files_to_get(self, files):        
        if not files:
            return

        fetch_files = set()
        for file in files:
            f_id = file.get("file_id")
            if f_id not in self.file_ids:
                fetch_files.add(f_id)
        return fetch_files

    @property
    def db(self):
        return self._db_data

    @property
    def server_data_dir(self):
        if self._data_dir:
            return self._data_dir
        raise ValueError("No data directory defined!")

    def get_file_metadata(self, directory):
        metadata_list = []

        try:
            for file_name in os.listdir(directory):
                filepath = os.path.join(directory, file_name)
                if os.path.isdir(filepath):
                    continue

                try:
                    with open(filepath, "rb") as f:
                        content = f.read()

                    file_size = os.path.getsize(filepath) / (1024 * 1024)

                    timestamp = int(
                        os.path.getmtime(filepath)
                    )  # this gets the file modification timestamp

                    hashBase = hashlib.sha256()
                    hashBase.update(content)
                    hashBase.update(str(timestamp).encode())
                    file_id = hashBase.hexdigest()

                    metadata = {
                        "file_name": file_name,
                        "file_size": file_size,
                        "file_id": file_id,
                        "file_owner": "bedis3",
                        "file_timestamp": timestamp,
                    }
                    self.file_ids[file_id] = file_name
                    metadata_list.append(metadata)
                except (IOError, OSError) as e:
                    logger.error(f"Error processing file {filepath}: {str(e)}")
        except OSError as e:
            logger.error(f"Error listing directory {directory}: {str(e)}")

        return metadata_list

    def _connect_to_db(self) -> None:
        """Connect to the database at the specified path."""
        db_path = self.db_dir

        try:
            if not os.path.exists(db_path):
                db_dir = os.path.dirname(db_path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir)

                meta_data = self.get_file_metadata(self.server_data_dir)
                self.save_json(meta_data, db_path)
                logger.info(f"Created new empty database file at: {db_path}")

            if not os.path.isfile(db_path):
                raise RuntimeError(f"Database path is not a file: {db_path}")

            logger.info(f"Successfully connected to: {db_path}")
            self._db_data = self.list_files()

            # Reset file_ids and repopulate from db_data
            self.file_ids = {}
            for file in self._db_data:
                if "file_id" in file and "file_name" in file:
                    self.file_ids[file["file_id"]] = file["file_name"]

            logger.info(f"Loaded {self._db_data} entries from database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            raise RuntimeError(f"Failed to connect to database: {str(e)}")

    def save_json(self, metadata_list, output_file):
        try:
            with open(output_file, "w") as f:
                json.dump(metadata_list, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error saving JSON to {output_file}: {str(e)}")
            return False
        
    def get_all_info(self, file_id:str):
        files = self._db_data
        for file in files:
            if file['file_id'] == file_id:
                return file
        return None

    def get_file_data(self, file_id: str) -> dict:
        
        if file_id not in self.file_ids:
            logger.warning(f"File ID {file_id} not found in database")
            return  {   
                    "type": "FILE_DATA",
                    "file_name": None,
                    "file_size": None,
                    "file_id": file_id,
                    "file_owner": None,
                    "file_timestamp": None,
                    "data": None,
                }
            
            
        file_name = self.file_ids[file_id]
        try:
            content = self.fm.get_file(file_name)
            f_info = self.get_all_info(file_id)        
            m_data = {   
                "type": "FILE_DATA",
                "file_name": file_name,
                "file_size": f_info["file_size"],
                "file_id": file_id,
                "file_owner": f_info["file_owner"],
                "file_timestamp": f_info["file_timestamp"],
                "data": content,
            }
            return m_data
        except Exception as e:
            logger.error(f"Error retrieving file {file_name}: {str(e)}")
    
        

    def __rm_file_by_id(self, files, file_id_to_remove):
        if not files or not file_id_to_remove:
            return files

        return [file for file in files if file.get("file_id") != file_id_to_remove]

    def remove_file(self, f_id: str):
        if not f_id:
            logger.error("Invalid file_id: None or empty")
            return False

        if f_id in self.file_ids:
            f_name = self.file_ids.get(f_id)
            try:
                if self.fm.delete_file(f_name):
                    self.file_ids.pop(f_id)  # remove the id
                    self._db_data = self.__rm_file_by_id(self._db_data, f_id)
                    return self.save_json(self._db_data, self.db_dir)
                else:
                    logger.error(
                        f"Delete request unsuccessful! File doesn't exist: {f_name}"
                    )
            except Exception as e:
                logger.error(f"Error while deleting file {f_name}: {str(e)}")
        else:
            logger.error(
                f"Request to remove file unsuccessful! The {f_id} doesn't exist in the database"
            )

        return False

    def list_files(self):
        try:
            with open(self.db_dir, "r") as f:
                data = f.read()
            return json.loads(data) if data else []
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Error reading database file: {str(e)}")
            return []

    def save_new_file(self, f_name, f_size, f_id, f_owner, f_tstmp, f_contnt  ) -> None:        
        # logger.debug(f"{f_name}, {f_size}, {f_id}, {f_owner}, {f_tstmp}, {len(f_contnt)}")
        
        if f_id not in self.file_ids:
            inp_data = {
                "file_name": f_name,
                "file_size": f_size,
                "file_id": f_id,
                "file_owner": f_owner,
                "file_timestamp": f_tstmp,
            }
            self.fm.save_file(f_name, f_contnt)
            self.file_ids[f_id] = f_name
            self._db_data.append(inp_data)
            logger.info(f"SUCCESS : saved {f_name} into the database!")
