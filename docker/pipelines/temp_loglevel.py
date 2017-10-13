from contextlib import contextmanager
import logging


@contextmanager
def temp_loglevel(level=logging.INFO):
    root_logging_handler = logging.root.handlers[0]
    old_level = root_logging_handler.level
    root_logging_handler.setLevel(level)
    yield
    root_logging_handler.setLevel(old_level)
