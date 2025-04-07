import random
import time

from utils.logger import Logger, LoggerClass

logger : LoggerClass = Logger(__name__).get_logger()



class Network_Tracker():

    def __init__(self):
        self.peers :dict = {}
        self.well_known = [
                            "silicon.cs.umanitoba.ca:8999",
                            # "eagle.cs.umanitoba.ca:8999",
                            # "grebe.cs.umanitoba.ca:8999",
                            # "hawk.cs.umanitoba.ca:8999"
                        ]

        self.ids : set = set()
        self.peer_and_addr : dict[str, tuple] =  {}
        self.peer_and_files : dict[str, list] = {} # store file_id : umnetid

    def save_id(self, input_id: str) -> None:
        self.ids.add(input_id)

    def save_announcement(self, f_id: str, user: str) -> None:
        if f_id not in self.peer_and_files: 
            self.peer_and_files.setdefault(f_id, [])
        self.peer_and_files[f_id].append(user)
    
    def id_exists(self, id ) :
        return id in self.ids

    def get_bootstrap(self) -> tuple [str, int]:
        boot_addr, boot_port = self.well_known[random.randint(0,len(self.well_known)-1)].split(":")
        return boot_addr, int(boot_port)

    def update_peers(self, peer: str, addr: tuple ):
        self.peers[peer] = time.time()
        self.peer_and_addr[peer] = addr
                
        curr_time = time.time()
        # logger.info(f"Peers: {self.peers}")

        for client, last_time in list(self.peers.items()):
            if curr_time - last_time >= 60:
                self.remove_peer(client)                
                
    def get_peer_addr(self, peer_name:str): 
        if peer_name not in self.peer_and_addr: 
            return None
        return self.peer_and_addr[peer_name]

    def remove_peer(self, peer):
        if peer in self.peers:
            logger.info(f"Removing peer: {peer}")
            del self.peers[peer]
            del self.peer_and_addr[peer]

    def has_peer(self, peer):
        return peer in self.peers
