"""
Central logging configuration for the whole project.

Call setup_logging() ONCE, at the program's entry point (e.g. top of app.py).
Every other module just does:

    import logging
    logger = logging.getLogger(__name__)
    logger.info("something happened")

...and the messages automatically pick up the format, level and destinations
configured here.
"""
import logging


def setup_logging(level: int = logging.INFO,
                  log_file: str = "reconciliation.log") -> None:
    # The format applied to every line.
    #   %(asctime)s  -> timestamp
    #   %(levelname)s-> INFO / WARNING / ERROR ...
    #   %(name)s     -> which module logged it (the getLogger(__name__) name)
    #   %(message)s  -> your actual message
    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers = [
        logging.StreamHandler(),                       # -> screen / console
        logging.FileHandler(log_file, encoding="utf-8"),  # -> a file you keep
    ]

    # force=True clears any previous config. Important for Streamlit, which
    # re-runs the script many times and would otherwise stack up handlers
    # (causing each line to print 2x, 3x, ...).
    logging.basicConfig(level=level, format=fmt, datefmt=datefmt,
                        handlers=handlers, force=True)
