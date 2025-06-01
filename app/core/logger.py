import logging
import os

def get_module_logger(module_name: str, log_file: str):
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.INFO)

    # Prevent adding multiple handlers if logger is called multiple times
    if not logger.handlers:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger