import logging
import os
from datetime import datetime

class Logger:
    def __init__(self, log_dir="logs", log_file=None):
        # Create logs directory if not exists
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Default log file name (with timestamp)
        if not log_file:
            log_file = f"{datetime.now().strftime('%Y-%m-%d')}.log"

        self.log_path = os.path.join(log_dir, log_file)

        # Configure logging
        logging.basicConfig(
            level=logging.DEBUG,  # Capture all levels (DEBUG and above)
            format="[%(asctime)s] [%(levelname)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[
                logging.FileHandler(self.log_path, mode='a'),
                logging.StreamHandler()  # Also prints to console
            ]
        )
        self.logger = logging.getLogger()

    def log_debug(self, message):
        self.logger.debug(message)

    def log_info(self, message):
        self.logger.info(message)

    def log_error(self, message):
        self.logger.error(message)

    def log_warning(self, message):
        self.logger.warning(message)

    def log_critical(self, message):
        self.logger.critical(message)
