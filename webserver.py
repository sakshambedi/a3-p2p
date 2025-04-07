import argparse
import sys

from utils.logger import Logger, LoggerClass
from webserver.webserver_protocol import webserver_protocol

logger: LoggerClass = Logger("Webserver").get_logger()


def main():
    parser = argparse.ArgumentParser(description="Simple Web Server")
    parser.add_argument(
        "--host",
        "-ht",
        type=str,
        default="",
        required=False,
        help="Port for the webserver.",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,         
        default=8042,
        help="Port for the webserver.",
    )
    parser.add_argument(
        "--fs_host",
        "-fsh",
        type=str,
        # required=True,
        default="",
        help="Port for the webserver.",
    )
    parser.add_argument(
        "--fs_port",
        "-fsp",
        type=int,
        # required=True,
        default=8041,
        help="Port for the webserver.",
    )
    args = parser.parse_args()
    Logger.configure(log_level="INFO")
    logger.info("RUNNIGN LOGGER")
    print(f"args : {args}")
    try:
        wb = webserver_protocol(args)
        wb.run()

    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
