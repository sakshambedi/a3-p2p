import logging
import os

__all__ = ["Logger", "LoggerClass"]
__version__ = "1.0.0"
__author__ = "Saksham Bedi"
__email__ = "me@sakshambedi.com"


class Logger:
    _instance = None
    _logger = None
    _configured = False

    def __new__(cls, name: str = __name__, log_dir : str | None = None):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)

            # Initialize logger in __new__
            cls._logger = logging.getLogger(name)
            cls._configured = False
            cls._log_dir = log_dir
        return cls._instance


    @classmethod
    def get_logger(cls) -> logging.Logger:
        assert cls._logger is not None, "Logger not initialized"
        return cls._logger

    @classmethod
    def configure(
            cls,
            log_dir: str | None = None,
            log_level: str | None = None,
            log_to_file: bool = False,
            format: str = "[%(asctime)s::%(filename)s::%(funcName)s:%(lineno)d] - %(levelname)s - %(message)s",
            datefmt: str = "%H:%M:%S",
        ):
            """
            Configure the logger with specified settings.

            Args:
            ----
            log_level (str): Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
            log_to_file (bool): Whether to log to a file
            log_file_path (str): Path to log file if log_to_file is True
            format (str): Log message format. Default includes module, function name, and line number.
            datefmt (str): Date format for log messages
            """
            if not cls._configured and cls._logger is not None and log_level is not None:
                # Clear any existing handlers
                cls._logger.handlers.clear()

                # Convert string log level to logging constant
                numeric_level = getattr(logging, log_level.upper(), None)
                if not isinstance(numeric_level, int):
                    raise ValueError(f"Invalid log level: {log_level}")

                # Set the base logger level
                cls._logger.setLevel(numeric_level)

                # Create and configure console handler
                console_handler = logging.StreamHandler()
                console_handler.setLevel(numeric_level)
                formatter = logging.Formatter(format, datefmt)
                console_handler.setFormatter(formatter)
                cls._logger.addHandler(console_handler)

                # Add file handler if requested
                if log_to_file:
                    if log_dir is None:
                        raise ValueError("log_dir must be specified when log_to_file is True")
                    file_handler = logging.FileHandler(os.path.join(log_dir, "log.txt"))
                    file_handler.setLevel(numeric_level)
                    file_handler.setFormatter(formatter)
                    cls._logger.addHandler(file_handler)

                cls._configured = True


# Create a typed alias
LoggerClass = logging.Logger
