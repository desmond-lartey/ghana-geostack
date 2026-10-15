"""One logger, configured once, used by every pipeline step."""

from __future__ import annotations

import logging
import os
import sys

_LEVEL = os.getenv("GHANA_LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=_LEVEL,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)

log = logging.getLogger("ghana")


def step(number: str, title: str) -> None:
    """Print a step banner. Pipelines are long-running and mostly watched by a
    human waiting to see whether to go and make tea."""
    line = "=" * 68
    log.info(line)
    log.info("Step %s — %s", number, title)
    log.info(line)
