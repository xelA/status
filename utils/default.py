import aiohttp

from datetime import datetime, timedelta, UTC


def utcnow() -> datetime:
    return datetime.now(UTC)


class DiscordStatus:
    def __init__(self, _cache_minutes: int = 2):
        self._data = {}
        self._last_fetch = None
        self._cache_minutes = _cache_minutes

    async def fetch(self) -> dict:
        if (
            self._last_fetch and
            utcnow() - self._last_fetch < timedelta(minutes=self._cache_minutes)
        ):
            return self._data

        async with aiohttp.ClientSession() as session:
            async with session.get("https://discordstatus.com/api/v2/status.json") as r:
                self._data = await r.json()

        self._last_fetch = utcnow()
        return self._data
