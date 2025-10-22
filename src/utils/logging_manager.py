import logging
from pathlib import Path

class LogFileManager:
    """Manages logging for the experiment session."""
    def __init__(self, log_file: Path, level=logging.INFO):
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename=log_file,
            filemode='w'
        )
        self.logger = logging.getLogger("ExperimentLogger")
        self.logger.info("LogFileManager initialized.")

    def log(self, message: str, level: str = "info") -> None:
        """Writes a message to the log file."""
        getattr(self.logger, level.lower(), self.logger.info)(message)