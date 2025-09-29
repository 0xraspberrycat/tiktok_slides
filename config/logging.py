import logging
from typing import Optional

# Custom levels
TRACE_LEVEL = 5  # Most detailed debugging
TESTING_LEVEL = 25  # Between INFO and WARNING

# Register custom levels
logging.addLevelName(TRACE_LEVEL, "TRACE")
logging.addLevelName(TESTING_LEVEL, "TESTING")


def trace(self, message, *args, **kwargs):
    if self.isEnabledFor(TRACE_LEVEL):
        self._log(TRACE_LEVEL, message, args, **kwargs)


def testing(self, message, *args, **kwargs):
    if self.isEnabledFor(TESTING_LEVEL):
        self._log(TESTING_LEVEL, message, args, **kwargs)


# Add custom methods to Logger
logging.Logger.trace = trace
logging.Logger.testing = testing


def setup_slide_logger(level: str = "INFO") -> logging.Logger:
    """Setup logger for slide manager

    Args:
        level: Log level (TRACE, DEBUG, INFO, TESTING, WARNING, ERROR, CRITICAL)
    """
    logger = logging.getLogger("slide_manager")

    # Only add handler if none exist
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - SlideManager - %(levelname)s - %(message)s",
            datefmt="%d/%m %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Convert string level to numeric level
    if level == "TRACE":
        log_level = TRACE_LEVEL
    elif level == "TESTING":
        log_level = TESTING_LEVEL
    elif hasattr(logging, level):
        log_level = getattr(logging, level)
    else:
        logger.warning(f"Invalid log level: {level}, using INFO")
        log_level = logging.INFO

    logger.setLevel(log_level)
    return logger


# Create default logger
logger = setup_slide_logger()
