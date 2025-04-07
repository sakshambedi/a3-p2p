PORT = 8040
HOST = ""
UMNET_ID = sbedi 
LOG_LEVEL = INFO
PEER = peer.py
ENVIRONMENT = PROD
.PHONY: run clean help webserver

all: help


run:
	python $(PEER) --port $(PORT) --um_id $(UMNET_ID) --log-level $(LOG_LEVEL) --environment $(ENVIRONMENT)

webserver:
	python webserver.py


clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf server_data/*

# Help message
help:
	@echo "P2P Network Client Makefile"
	@echo "Usage:"
	@echo "  make run              - Run client with default settings (port 8040, DEBUG level)"
	@echo "  make run PORT=8080    - Run client on port 8080"
	@echo "  make run LOG_LEVEL=INFO - Run client with INFO log level"
	@echo "  make clean            - Remove Python cache files"
