from datetime import datetime, UTC


def utcnow() -> datetime:
    """ Return the current UTC time. """
    return datetime.now(UTC)
