import random
import time

from utils.logger import Logger, LoggerClass

logger: LoggerClass = Logger(__name__).get_logger()


class Network_Tracker:
    def __init__(self):
        self.well_known = [
            "silicon.cs.umanitoba.ca:8999",
            "eagle.cs.umanitoba.ca:8999",
            "grebe.cs.umanitoba.ca:8999",
            "hawk.cs.umanitoba.ca:8999",
        ]

        self.peers: dict = {}  # store peer: time
        self.ids: set = set()
        self.peer_and_addr: dict[str, tuple] = {}
        self.addr_and_peer: dict[str, str] = {}
        

    def get_peers_status(self):
        all_peers = []

        for peer in self.well_known:
            if peer in self.peers:
                last_seen = int(time.time() - self.peers[peer])
                addr, port = self.peer_and_addr[peer]
                all_peers.append(
                    {
                        "peer_name": peer,
                        "host": addr,
                        "port": str(port),
                        "last_seen": last_seen,
                    }
                )

        for peer in self.peers:
            if self.has_peer(peer):
                last_seen = int(time.time() - self.peers[peer])
                addr, port = self.peer_and_addr[peer]
                all_peers.append(
                    {
                        "peer_name": peer,
                        "host": addr,
                        "port": str(port),
                        "last_seen": last_seen,
                    }
                )
        return all_peers
    
    def get_all_peers(self):        
        return list(self.well_known) + list(self.addr_and_peer.keys())

    def save_id(self, input_id: str) -> None:
        self.ids.add(input_id)

    def id_exists(self, id):
        return id in self.ids

    def get_bootstrap(self) -> tuple[str, int]:
        return self.well_known

    def update_peers(self, peer: str, addr: tuple):
        self.peers[peer] = time.time()
        self.peer_and_addr[peer] = addr
        p_addr,p_host = addr
        p_full_addr = f"{p_addr}:{str(p_host)}"
        self.addr_and_peer[p_full_addr] = peer
        
        curr_time = time.time()

        for client, last_time in list(self.peers.items()):
            if curr_time - last_time >= 60:
                self.remove_peer(client)

        logger.info(f"Active Peers: {list(self.peers.keys())}")

    def get_peer_addr(self, peer_name: str):
        if peer_name not in self.peer_and_addr:
            return None
        return self.peer_and_addr[peer_name]

    def remove_peer(self, peer):
        if peer in self.peers:
            logger.info(f"Removing peer: {peer}")
            addr = self.peer_and_addr.get(peer)
            if addr:
                p_addr, p_host = addr
                p_full_addr = f"{p_addr}:{str(p_host)}"
                del self.addr_and_peer[p_full_addr]
            del self.peers[peer]
            del self.peer_and_addr[peer]

            
    def get_peer_from_addr(self, addr: tuple) -> str: 
        p_addr,p_host = addr
        p_full_addr = f"{p_addr}:{str(p_host)}"
        logger.info(f"addr_and_peer:{self.addr_and_peer}")
        return self.addr_and_peer.get(p_full_addr, None)
        

    def has_peer(self, peer):
        return peer in self.peers
