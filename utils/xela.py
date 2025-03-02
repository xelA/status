import aiohttp
import asyncio

from datetime import datetime, timedelta
from postgreslite import PoolConnection

from utils import default


class xelAAPI:
    def __init__(self, *, db: PoolConnection, config: dict):
        self.db: PoolConnection = db
        self.config = config

        self._data: dict = {}
        self._last_fetch: datetime | None = None

        self.cache_seconds: int = config["XELA_CACHE_SECONDS"]
        self.cache_data: list[dict] = []

        self.update_cache()

    def __str__(self) -> str:
        return f"{self.username}#{self.discriminator}"

    def __int__(self) -> int:
        return int(self.id)

    @property
    def me(self) -> dict:
        return self._data.get("@me", {})

    @property
    def last_reboot(self) -> int:
        return self._data.get("last_reboot", 0)

    @property
    def ram(self) -> int:
        return self._data.get("ram", 0)

    @property
    def database(self) -> int:
        return self._data.get("database", 0)

    @property
    def server_installs(self) -> int:
        return self._data.get("server_installs", 0)

    @property
    def user_installs(self) -> int:
        return self._data.get("user_installs", 0)

    @property
    def users(self) -> int:
        return self._data.get("users", 0)

    @property
    def avg_users_server(self) -> int:
        return self._data.get("avg_users_server", 0)

    @property
    def ping(self) -> dict:
        return self._data.get("ping", {})

    @property
    def ping_ws(self) -> int:
        return self.ping.get("ws", 0)

    @property
    def ping_rest(self) -> int:
        return self.ping.get("rest", 0)

    @property
    def id(self) -> int:
        return self.me.get("id", 1337)

    @property
    def avatar(self) -> str:
        return self.me.get("avatar", "")

    @property
    def discriminator(self) -> str:
        return self.me.get("discriminator", "0000")

    @property
    def username(self) -> str:
        return self.me.get("username", "NotFound")

    @property
    def avatar_url(self) -> str:
        return "https://cdn.discordapp.com/avatars/{id}/{avatar}.{format}?size={size}".format(
            id=self.id, avatar=self.avatar, format="png", size=512
        )

    async def _background_task(self):
        while True:
            await asyncio.sleep(5)
            await self.fetch_data()

    async def fetch_data(self) -> tuple[dict, bool]:
        """ Fetch data from the bot API (False = cache, True = fetch) """
        if (
            self._last_fetch and
            default.utcnow() - self._last_fetch < timedelta(seconds=self.cache_seconds)
        ):
            return (self._data, False)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://127.0.0.1:{self.config['XELA_PORT']}/bot/stats"
                ) as r:
                    self._data = await r.json()
        except Exception as e:
            print(e)
            new_fake_data = self._data.copy()
            new_fake_data["ping"] = {"type": "ms", "ws": 0, "rest": 0}
            self._data = new_fake_data
            del new_fake_data

        self._last_fetch = default.utcnow()

        self.update_data()

        return (self._data, True)

    def update_data(self):
        self.db.execute(
            "INSERT INTO ping (server_installs, user_installs, ping_ws, ping_rest) "
            "VALUES (?, ?, ?, ?)",
            self.server_installs,
            self.user_installs,
            self.ping_ws,
            self.ping_rest
        )

        self.update_cache()

    def update_cache(self):
        self.cache_data = self.db.fetch(
            "SELECT * FROM ping ORDER BY created_at DESC LIMIT 25"
        )
