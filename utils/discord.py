import aiohttp
import asyncio

from datetime import datetime, timedelta
from postgreslite import PoolConnection

from utils import default


class StatusIndicator:
    def __init__(self, data: dict):
        self.url = "https://discordstatus.com/"

        self.name: str | None = data.get("name")
        self.status = data.get("status")
        self.impact = data.get("impact")
        self.description = data.get("description")

    def has_issues(self) -> bool:
        return self.status not in (None, "none", "operational")

    def reset(self) -> None:
        self.name = None
        self.status = None
        self.impact = None
        self.description = None

    def update(self, data: dict | str) -> None:
        if not isinstance(data, dict):
            return

        incidents = data.get("incidents", [])
        if not isinstance(incidents, list):
            return

        # No unresolved incidents reported
        if not incidents:
            self.reset()
            return

        latest_incident = incidents[0]
        incident_updates = next(
            (u for u in latest_incident.get("incident_updates", [])),
            {}
        )

        self.name = latest_incident.get("name", "unknown")
        self.status = latest_incident.get("status", "none")
        self.impact = latest_incident.get("impact", "none")
        self.description = incident_updates.get("body", "No description available.")

    def to_dict(self) -> dict:
        return {
            "has_issues": self.has_issues(),
            "name": self.name,
            "status": self.status,
            "impact": self.impact,
            "description": self.description,
            "url": self.url
        }

    @classmethod
    def none(cls):
        return cls({})


class DiscordStatus:
    def __init__(self):
        self.data_status = StatusIndicator.none()
        self.data_metric = {}

    @property
    def last_ping(self) -> int:
        data = self.data_metric.get("metrics", [{}])[0].get("data", [{}])[-1]
        return data.get("value", 0)

    async def fetch(self) -> None:
        async with aiohttp.ClientSession() as session:
            try:
                # Fetch downtime
                async with session.get("https://discordstatus.com/api/v2/incidents/unresolved.json") as r:
                    self.data_status.update(await r.json())
            except Exception as e:
                print(e)

            try:
                # Fetch metrics
                async with session.get("https://discordstatus.com/metrics-display/5k2rt9f7pmny/day.json") as r:
                    self.data_metric = await r.json()
            except Exception as e:
                print(e)


class xelAAPI:  # noqa: N801
    def __init__(self, *, db: PoolConnection, config: dict):
        self.db: PoolConnection = db
        self.config = config

        self.discord = DiscordStatus()

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
    def ping_discord(self) -> int:
        return self.discord.last_ping

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
    def interactions(self) -> dict[str, float]:
        data = self._data.get("interactions", {})
        return {
            "per_second": data.get("per_second", 0.0),
            "per_minute": data.get("per_minute", 0.0),
            "per_hour": data.get("per_hour", 0.0)
        }

    @property
    def avatar_url(self) -> str:
        return "https://cdn.discordapp.com/avatars/{id}/{avatar}.{format}?size={size}".format(
            id=self.id, avatar=self.avatar, format="png", size=512
        )

    def api_latest(self) -> dict:
        """ API for the latest data. """
        return {
            "discord_status": self.discord.data_status.to_dict(),
            "ping_ws": self.ping_ws,
            "ping_rest": self.ping_rest,
            "ping_discord": self.ping_discord,
            "server_installs": self.server_installs,
            "user_installs": self.user_installs,
            "ram": self.ram,
            "last_reboot": self.last_reboot,
            "viewable_users": self.users,
            "avg_users_server": self.avg_users_server,
            "interactions": self.interactions
        }

    def api_history(self) -> list[dict]:
        """ API for the history data. """
        return [
            {
                "server_installs": g["server_installs"],
                "user_installs": g["user_installs"],
                "ping_ws": g["ping_ws"],
                "ping_discord": g["ping_discord"],
                "ping_rest": g["ping_rest"],
                "created_at": g["created_at"],  # Ensure it's ISO format
            }
            for g in self.cache_data
        ]

    async def _background_task(self):
        while True:
            await asyncio.sleep(5)
            await self.fetch_data()

    async def fetch_data(self) -> tuple[dict, bool]:
        """ Fetch data from the bot API (False = cache, True = fetch). """
        if (
            self._last_fetch and
            default.utcnow() - self._last_fetch < timedelta(seconds=self.cache_seconds)
        ):
            return (self._data, False)

        try:
            async with aiohttp.ClientSession() as session, session.get(
                f"http://127.0.0.1:{self.config['XELA_PORT']}/bot/stats"
            ) as r:
                self._data = await r.json()
        except Exception as e:
            print(e)
            new_fake_data = self._data.copy()
            new_fake_data["ping"] = {"type": "ms", "ws": 0, "rest": 0}
            self._data = new_fake_data
            del new_fake_data

        try:
            await self.discord.fetch()
        except Exception as e:
            print(e)

        self._last_fetch = default.utcnow()

        self.update_data()

        return (self._data, True)

    def update_data(self):
        self.db.execute(
            "INSERT INTO ping (server_installs, user_installs, ping_ws, ping_rest, ping_discord) "
            "VALUES (?, ?, ?, ?, ?)",
            self.server_installs,
            self.user_installs,
            self.ping_ws,
            self.ping_rest,
            self.discord.last_ping
        )

        self.update_cache()

    def update_cache(self):
        self.cache_data = self.db.fetch(
            "SELECT * FROM ping ORDER BY created_at DESC LIMIT 30"
        )
