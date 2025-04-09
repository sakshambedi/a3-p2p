# P2P Network Client

A peer-to-peer network client implementation that allows for distributed communication between nodes.

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Running the Peer Client](#running-the-peer-client)  
  - [Web Server](#web-server)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Common Questions](#common-questions)
- [Bonus](#BONUS)



## Overview

This project implements a peer-to-peer network client that allows nodes to communicate directly with each other without requiring a central server. It includes a peer client implementation and a web server interface for monitoring and control.

## Prerequisites

- Python 3.6 or higher
- Required Python packages (list these in a requirements.txt file)

## Configuration

The project uses the following default configuration:
- Port: 8040
- Port: 8042 for website from A2
- Host: (empty string - binds to all available interfaces)
- UMNET ID: bedis3
- Log Level: INFO
- Environment: PROD

You can modify these settings by:
1. Editing the Makefile
2. Passing parameters when running make commands
3. Setting environment variables

## Usage

### Running the Peer Client

To run the peer client with default settings:

```
make run
```

To run with different log level:

```
make run LOG_LEVEL=DEBUG
```


### Web Server

After starting the peer client, you can launch the web server interface:

```
make webserver
```

Access the web interface by opening a browser and navigating to: `http://localhost:8042` 

### Dummy Mode

For testing purposes, you can run a dummy client:

```
make dummy
```

This will start a dummy client on port 8999.

## Project Structure

- `peer.py` - Main peer implementation
- `webserver.py` - Web server interface
- `dummy.py` - Dummy client for testing
- Other supporting files and modules

## Troubleshooting

### Common Issues

1. **Port already in use**
   - Try specifying a different port: `make run PORT=8050`
   - Check for any processes using the default port: `lsof -i :8040`

2. **Connection issues**
   - Verify network settings
   - Check firewall configurations
   - Ensure the peer address is correctly specified

### Cleaning Up

If you encounter issues with Python cache files, clean them:

```
make clean
```

## Common Questions

Q1) How to start your peer, any command line arguments, and what to expect. How long does it take to synchronize, what will we see when it is synchronized
To start the peer, follow the Usage section of the document. The synchronization starts right away, as soon as I get my first GOSSIP_REPLY, but i'll give me 10 secs to fetch all the files and the latecy from other peers of the network for it to catch up.You will logs message(assuming to keep the log_level=INFO(default in the makefile)). The logs tells you what request is being made to other peers and what they are requesting from me. Also shows logs if there an inappropriate request from other peers.


Q2) Tell us where your metadata code is - the part that builds your metadata when syncing. Give us the name of the file, and the line number with a 2 sentence description of how it does it.

Answer : The meta data of the p2p network gets built in the db_manager.py.
The metadata code that builds `self.__db_data` during syncing is located in the file `db_manager.py` at line 138, within the `_connect_to_db` method. This method initializes the database by either creating a new one with metadata from `get_file_metadata` if the database file doesn’t exist, or loading existing data from the JSON file via `list_files` and assigning it to `self._db_data`. 
I get GOSSIP_REPLY from the peers on the network with the file information. SinceI already know what files I have, I request the files I need to get in the `req_file()` function in `network.py` at line number 230. It sends out request to get files. Once I get the files I save them in the directory. 


Q3) 2 sentences on how you clean up peers, give us the file name and line number for this, too
Anytime I get a gossip message I call the `update_peers` function in `network_tracker.py` since I am ought to get a GOSSIP every short interval. The `update_peers` function on line 66 in the `network_tracker.py` class is responsible for managing and updating the list of active peers by recording a peer’s activity and removing peers that have been inactive for more than 60 secs. It takes two parameters: peer (a string representing the peer’s name) and addr. First, it updates the `self.peers` dictionary by assigning the current timestamp (`time.time()`) to the peer, marking it as recently active. Then, it stores the peer’s address in the self.peer_and_addr dictionary for name-to-address lookup and constructs a full address string (e.g., "host:port") to map back to the peer in the `self.addr_and_peer` dictionary for address-to-name lookup. Next, it checks all peers in self.peers against the current time; if any peer’s last-seen timestamp is 60 or more seconds old, it calls remove_peer to delete that peer from all tracking dictionaries (`self.peers`, `self.peer_and_addr`, and `self.addr_and_peer`). This process ensures the tracker maintains an accurate, up-to-date record of peers and their statuses, pruning inactive ones efficiently.

## BONUS

This assignment has implemented the extra 10\% by connecting the A3 to A2. Please give me the extra 10% for the assignment.
Full connection of your A2 with P2P database +10%. I support all the endpoints in the A2 restFul API.
NOTE: THE website doesnt show the the file_id on the website, thats a design choice for easy readabily. the console prints the entire files DS from the peer2peer network with the file_id 
