import logging
import sys


def configure_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("aura")
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
    )
    handler.setFormatter(fmt)
    if not logger.handlers:
        logger.addHandler(handler)
    logger.propagate = False
    return logger
