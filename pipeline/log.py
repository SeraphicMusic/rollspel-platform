"""Loggning per bok: fil (DEBUG) + konsol (INFO). Släktforskaren-mönstret."""
import logging
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s %(message)s"


def setup_logging(workdir):
    log = logging.getLogger("rippare")
    if log.handlers:
        return log
    log.setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(_FORMAT))
    log.addHandler(console)

    if workdir is not None:
        logdir = Path(workdir) / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(logdir / "pipeline.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(_FORMAT))
        log.addHandler(fh)
    return log
