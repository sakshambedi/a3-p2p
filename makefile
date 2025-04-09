PORT = 8040
HOST = ""
UMNET_ID = bedis3 
LOG_LEVEL = INFO
PEER = peer.py
ENVIRONMENT = PROD
.PHONY: run clean help webserver

all: help


run:
	python $(PEER) --port $(PORT) --um_id $(UMNET_ID) --log-level $(LOG_LEVEL) --environment $(ENVIRONMENT)

dev:
	python $(PEER) --port $(PORT) --um_id $(UMNET_ID) --log-level $(LOG_LEVEL) --environment DEV 

dummy:
	python dummy.py --port 8999

webserver:
	python webserver.py


clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete	


help:
	@echo "P2P Network Client Makefile"
	@echo "Usage:"
	@echo "  make run                  - Run the peer client with default settings (port 8040, INFO log level, PROD environment)"
	@echo "  make run PORT=<port>      - Run the peer client on a specified port"
	@echo "  make run LOG_LEVEL=<lvl>  - Run the peer client with a specified log level (e.g., INFO, DEBUG)"
	@echo "  make dev                  - Run the peer client in the DEV environment"
	@echo "  make webserver            - Start the web server (run after starting the peer client)"
	@echo "  make clean                - Remove Python cache files"
