import logging
import json
import sys
import time

from aiohttp import web
from jinja2 import Environment, FileSystemLoader
from datetime import datetime, UTC

jinja_engine = Environment(loader=FileSystemLoader("templates"), autoescape=True)


def json_response(data: dict | list, *, status: int = 200) -> web.Response:
    """ Simplify the JSON response output. """
    return web.Response(
        text=json.dumps(data),
        content_type="application/json",
        status=status,
    )


def html_response(filename: str, **kwargs):
    """ Shortcut to render HTML files like Flask-style. """
    html = jinja_engine.get_template(filename).render(**kwargs)
    return web.Response(text=html, content_type="text/html")


def utcnow() -> datetime:
    """ Return the current UTC time. """
    return datetime.now(UTC)


def setup_logging() -> logging.Logger:
    """ Configure and return the xela_status logger. """
    logger = logging.getLogger("xela_status")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(handler)
    return logger


def unix_timestamp(timestamp: str | datetime | float | int) -> float | int:
    """
    Convert a timestamp to a unix timestamp.

    Parameters
    ----------
    timestamp:
        The timestamp to convert.

    Returns
    -------
        The unix timestamp.
    """
    if isinstance(timestamp, str):
        fmt = "%Y-%m-%d" if len(timestamp) == 10 else "%Y-%m-%d %H:%M:%S"
        return time.mktime(datetime.strptime(timestamp, fmt).timetuple())

    if isinstance(timestamp, datetime):
        return time.mktime(timestamp.timetuple())

    return timestamp
