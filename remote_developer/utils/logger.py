"""Logger module."""

import logging
import sys
from enum import Enum


class LogLevel(Enum):
    """
    Enumeration for log levels.

    This enum provides a type-safe way to represent different log levels.
    Each member corresponds to a logging level from the Python `logging` module.

    Members:
        DEBUG: Represents the DEBUG log level.
        INFO: Represents the INFO log level.
        WARNING: Represents the WARNING log level.
        ERROR: Represents the ERROR log level.
        CRITICAL: Represents the CRITICAL log level.
    """

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class Color:
    """
    Defines ANSI escape codes for colored terminal output.

    This class provides constants for various colors that can be used to
    colorize log messages in the terminal.

    Attributes:
        RESET (str): Resets the color to default.
        RED (str): ANSI escape code for red color.
        GREEN (str): ANSI escape code for green color.
        YELLOW (str): ANSI escape code for yellow color.
        BLUE (str): ANSI escape code for blue color.
        MAGENTA (str): ANSI escape code for magenta color.
        CYAN (str): ANSI escape code for cyan color.
        WHITE (str): ANSI escape code for white color.
    """

    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"


class ColoredFormatter(logging.Formatter):
    """
    A custom formatter that adds colors to log messages based on their level.

    This formatter inherits from `logging.Formatter` and overrides the `format`
    method to add ANSI escape codes to log messages based on their log level.

    Attributes:
        COLOR_MAP (dict): A dictionary mapping log levels to their corresponding colors.
    """

    COLOR_MAP = {
        logging.DEBUG: Color.CYAN,
        logging.INFO: Color.GREEN,
        logging.WARNING: Color.YELLOW,
        logging.ERROR: Color.RED,
        logging.CRITICAL: Color.MAGENTA,
    }

    def format(self, record):
        """
        Formats the log record with color.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: The formatted log message with color.
        """
        log_color = self.COLOR_MAP.get(record.levelno, Color.WHITE)
        message = super().format(record)
        return f"{log_color}{message}{Color.RESET}"


class Logger:
    """
    A custom logger class that abstracts the Python `logging` module.

    This class provides a simplified interface for logging messages with
    different levels and optional colorization. It uses the `logging` module
    under the hood but provides a more convenient way to create and use loggers.

    Attributes:
        logger (logging.Logger): The underlying logger instance.
    """

    def __init__(self, name: str, level: LogLevel = LogLevel.DEBUG, colorize: bool = True):
        """
        Initializes a new logger instance.

        Args:
            name (str): The name of the logger.
            level (LogLevel, optional): The minimum log level to record. Defaults to LogLevel.DEBUG.
            colorize (bool, optional): Whether to colorize the log output. Defaults to True.
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level.value)

        handler = logging.StreamHandler(sys.stdout)
        if colorize:
            formatter = ColoredFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        else:
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)

        self.logger.addHandler(handler)

    def log(self, level: LogLevel, message: str, *args, **kwargs):
        """
        Logs a message with the specified log level.

        Args:
            level (LogLevel): The log level of the message.
            message (str): The message to log.
            *args: Additional arguments to pass to the logging function.
            **kwargs: Additional keyword arguments to pass to the logging function.
        """
        self.logger.log(level.value, message, *args, **kwargs)

    def debug(self, message: str, *args, **kwargs):
        """
        Logs a message with the DEBUG log level.

        Args:
            message (str): The message to log.
            *args: Additional arguments to pass to the logging function.
            **kwargs: Additional keyword arguments to pass to the logging function.
        """
        self.log(LogLevel.DEBUG, message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        """
        Logs a message with the INFO log level.

        Args:
            message (str): The message to log.
            *args: Additional arguments to pass to the logging function.
            **kwargs: Additional keyword arguments to pass to the logging function.
        """
        self.log(LogLevel.INFO, message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        """
        Logs a message with the WARNING log level.

        Args:
            message (str): The message to log.
            *args: Additional arguments to pass to the logging function.
            **kwargs: Additional keyword arguments to pass to the logging function.
        """
        self.log(LogLevel.WARNING, message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        """
        Logs a message with the ERROR log level.

        Args:
            message (str): The message to log.
            *args: Additional arguments to pass to the logging function.
            **kwargs: Additional keyword arguments to pass to the logging function.
        """
        self.log(LogLevel.ERROR, message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        """
        Logs a message with the CRITICAL log level.

        Args:
            message (str): The message to log.
            *args: Additional arguments to pass to the logging function.
            **kwargs: Additional keyword arguments to pass to the logging function.
        """
        self.log(LogLevel.CRITICAL, message, *args, **kwargs)


def get_level_from_env():
    """Retrieves the log level from environment variables."""
    import os

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    if level_name not in LogLevel.__members__:
        raise ValueError(
            f"Invalid log level: {level_name}. Valid levels are: {', '.join(LogLevel.__members__.keys())}"
        )
    return LogLevel[level_name]
