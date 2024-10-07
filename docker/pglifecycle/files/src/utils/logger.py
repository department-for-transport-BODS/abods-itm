import logging
from .config import LOG_LEVEL


logging.basicConfig(format="%(levelname)s,%(message)s")
log = logging.getLogger()
log.setLevel(LOG_LEVEL)
