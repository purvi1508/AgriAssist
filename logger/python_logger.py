import inspect
import logging
import os
from abc import ABC, abstractmethod

import structlog

# Global logger instance
_logger = None


def setup_logger(processors=None):
    """Set up the global logger instance."""
    global _logger
    if _logger is None:
        _logger = AgriLogger(processors)
    return _logger


def get_logger():
    """Get the global logger instance."""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger


class LogProcessor(ABC):
    """Abstract base class for log processors."""

    @abstractmethod
    def process(self, logger, method_name, event_dict):
        """Process the log event dictionary."""
        pass


class KeyRenameProcessor(LogProcessor):
    """Processor to rename keys in the log event dictionary."""

    def __init__(self, key_mapping):
        """Initialize with a mapping of old keys to new keys."""
        self.key_mapping = key_mapping

    def process(self, logger, method_name, event_dict):
        """Rename keys in the event dictionary based on the mapping."""
        for old_key, new_key in self.key_mapping.items():
            if old_key in event_dict:
                # Ensure level is uppercase if being renamed to levelname
                if old_key == "level" and new_key == "levelname":
                    event_dict[new_key] = event_dict.pop(old_key).upper()
                else:
                    event_dict[new_key] = event_dict.pop(old_key)
        return event_dict


class LoggerConfig:
    """Configuration class for setting up the logger."""

    @staticmethod
    def get_default_processors():
        """Return the default processors for the logger."""
        return [
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.processors.add_log_level,
            structlog.contextvars.merge_contextvars,
            KeyRenameProcessor(
                {
                    "timestamp": "asctime",
                    "level": "levelname",
                    "event": "message",
                    "logger": "name",
                }
            ).process,
            structlog.processors.JSONRenderer(),
        ]


class AgriLogger:
    """A structured logger for the application."""

    def __init__(self, processors=None):
        """Initialize the logger with specified processors."""
        self._setup_library_logging()
        self.logger = self._configure_logger(
            processors or LoggerConfig.get_default_processors()
        )

    def _setup_library_logging(self):
        """Set logger levels for specific libraries."""
        # # Configure the root logger
        # logging.basicConfig(level=logging.INFO)

        # Set specific log levels for libraries
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)

    def _configure_logger(self, processors):
        """Configure the logger with the given processors."""
        structlog.configure(
            processors=processors,
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,
        )
        return structlog.get_logger()

    def __getattr__(self, name):
        """
        Dynamically handle calls to logger.info(), logger.error(), etc.
        """
        if name in ["info", "error", "warning", "debug", "critical"]:

            def log_method(event, **kwargs):
                return self.log(name, event, **kwargs)

            return log_method
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def log(self, level, event, **kwargs):
        """Internal method to handle logging at different levels."""
        caller_info = self.get_caller_info()
        level = level.lower()

        if level == "info":
            # For info level, only include function name and filename
            log_data = {
                "levelname": level.upper(),
                "event": event,
                "filename": caller_info.get("filename"),
                "name": caller_info.get("name"),
                **kwargs,
            }
        else:
            # For other levels, include all caller info
            log_data = {
                "levelname": level.upper(),
                "event": event,
                **caller_info,
                **kwargs,
            }

        getattr(self.logger, level)(**log_data)

    def get_caller_info(self):
        """Retrieve information about the caller of the log method."""
        current_frame = inspect.currentframe()
        try:
            # Go up the call stack to find the caller
            caller_frame = current_frame.f_back.f_back  # Skip the log() method frame

            while caller_frame:
                filename = caller_frame.f_code.co_filename
                if filename not in (__file__, structlog.__file__):
                    return {
                        "filename": os.path.basename(filename),
                        "name": caller_frame.f_globals.get("__name__", ""),
                        "lineno": caller_frame.f_lineno,
                        "function": caller_frame.f_code.co_name,
                    }
                caller_frame = caller_frame.f_back

        finally:
            del current_frame
