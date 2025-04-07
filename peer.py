import argparse

from core.network import Peer_Protocol
from utils.logger import Logger, LoggerClass

logger: LoggerClass = Logger("p2p-client").get_logger()


def main():
    parser = argparse.ArgumentParser(description="2P2 Network Protocol")
    parser.add_argument(
        "--log-level",
        "-ll",
        type=str,
        required=False,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="DEBUG",
        help="Logging level",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        required=True,
        default=8040,
        help="Set the port to run the client.",
    )
    parser.add_argument(
        "--host", "-ho", type=str, default="", help="Set the port to run the client."
    )
    parser.add_argument(
        "--um_id",
        "-id",
        type=str,
        required=True,
        help="Set the UMNet ID for sending in requests",
    )
    parser.add_argument(
        "--db_file",
        "-d",
        type=str,
        default=".db.json",
        help="Set the UMNet ID for sending in requests",
    )
    parser.add_argument(
        "--server_data",
        "-sd",
        type=str,
        default="./server_data",
        help="Set the UMNet ID for sending in requests",
    )
    parser.add_argument(
        "--environment",
        "-e",
        type=str,
        default = "DEV",        
        choices=["DEV", "PROD"],
        help="Set the UMNet ID for sending in requests",
    )

    args = parser.parse_args()
    Logger.configure(log_level=args.log_level)

    peer = None
    try:
        logger.info(f"Starting P2P Peer with ID: {args.um_id}")        
        protocol = Peer_Protocol(args)                    
        protocol.run_server_loop()
            
    except KeyboardInterrupt:
        logger.info("Shutdown requested via KeyboardInterrupt.")
        
    except Exception as e:
        logger.exception(f"An error occurred during peer initialization or main loop: {e}")
        # if peer:
        #     peer.shutdown()
    finally:
        logger.info("Peer application exiting.")


if __name__ == "__main__":
    main()
