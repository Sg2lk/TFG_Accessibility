import logging
from logging.handlers import RotatingFileHandler

from src.app_paths import get_log_file_path


_CONFIGURED = False


def setup_logging():
    global _CONFIGURED

    log_file_path = get_log_file_path()

    if _CONFIGURED:
        return log_file_path

    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    file_handler._tfg_accessibility_handler = True

    root_logger.handlers = [
        handler
        for handler in root_logger.handlers
        if not getattr(handler, "_tfg_accessibility_handler", False)
    ]
    root_logger.addHandler(file_handler)

    logging.captureWarnings(True)

    _CONFIGURED = True
    return log_file_path
