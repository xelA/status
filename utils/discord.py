import aiohttp
import asyncio
import logging

from datetime import datetime, timedelta
from postgreslite import PoolConnection

from utils import default

_log = logging.getLogger("xela_status")


class StatusIndicator:
    def __init__(self, data: dict):
        self.url = "https://discordstatus.com/"

        self.name: str | None = data.get("name")
        self.status = data.get("status")
        self.impact = data.get("impact")
        self.description = data.get("description")
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")

    def has_issues(self) -> bool:
        return self.status not in (None, "none", "operational")

    def reset(self) -> None:
        self.name = None
        self.status = None
        self.impact = None
        self.description = None
        self.created_at = None
        self.updated_at = None

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

        impact = latest_incident.get("impact", "none")
        if impact == "none":
            self.reset()
            return

        self.name = latest_incident.get("name", "unknown")
        self.impact = impact
        self.status = latest_incident.get("status", "none")
        self.description = incident_updates.get("body", "No description available.")
        self.created_at = latest_incident.get("created_at")
        self.updated_at = latest_incident.get("updated_at")

    def to_dict(self) -> dict:
        return {
            "has_issues": self.has_issues(),
            "name": self.name,
            "status": self.status,
            "impact": self.impact,
            "description": self.description,
            "created_at": str(self.created_at),
            "updated_at": self.updated_at,
            "url": self.url,
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
                _log.error("Failed to fetch discord status incidents", exc_info=e)

            try:
                # Fetch metrics
                async with session.get("https://discordstatus.com/metrics-display/5k2rt9f7pmny/day.json") as r:
                    self.data_metric = await r.json()
            except Exception as e:
                _log.error("Failed to fetch discord status metrics", exc_info=e)


class xelAAPI:  # noqa: N801
    def __init__(self, *, db: PoolConnection, config: dict):
        self.db: PoolConnection = db
        self.config = config

        self.discord = DiscordStatus()

        self._data: dict = {}
        self._last_fetch: datetime | None = None

        self.cache_seconds: int = config["XELA_CACHE_SECONDS"]

        self.cache_data: list[dict] = []
        self.daily_cache_data: list[dict] = []

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
    def ping_discord(self) -> int:
        return self.discord.last_ping

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

    def api_user(self) -> dict:
        """ API for the bot user data. """
        return {
            "id": self.id,
            "username": self.username,
            "discriminator": self.discriminator or None,
            "avatar": self.avatar,
            "avatar_url": self.avatar_url,
        }

    def api_latest(self) -> dict:
        """ API for the latest data. """
        return {
            "discord_status": self.discord.data_status.to_dict(),
            "ping_ws": self.ping_ws,
            "ping_rest": self.ping_rest,
            "ping_discord": self.ping_discord,
            "server_installs": self.server_installs,
            "user_installs": self.user_installs,
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
                "ping_rest": g["ping_rest"],
                "ping_discord": g["ping_discord"],
                "created_at": str(g["created_at"]),  # Ensure it's ISO format
            }
            for g in self.cache_data
        ]

    def api_daily(self) -> list[dict]:
        """ API for the daily average data (past 30 days). """
        return [
            {
                "day": g["day"],
                "avg_ping_ws": round(g["avg_ws"]),
                "avg_ping_rest": round(g["avg_rest"]),
                "avg_ping_discord": round(g["avg_discord"]),
            }
            for g in self.daily_cache_data
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
                f"http://127.0.0.1:{self.config['XELA_PORT']}/bot/stats",
                headers={
                    "X-API-Key": self.config["XELA_API_KEY"]
                }
            ) as r:
                self._data = await r.json()
        except Exception as e:
            _log.error("Failed to fetch internal API data", exc_info=e)
            new_fake_data = self._data.copy()
            new_fake_data["ping"] = {"type": "ms", "ws": 0, "rest": 0}
            self._data = new_fake_data
            del new_fake_data

        try:
            await self.discord.fetch()
        except Exception as e:
            _log.error("Discord fetching failed", exc_info=e)

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
            self.ping_discord,
        )

        self.update_cache()

    def update_cache(self):
        self.cache_data = self.db.fetch(
            "SELECT * FROM ping ORDER BY created_at DESC LIMIT 30"
        )
        self.daily_cache_data = self.db.fetch(
            "SELECT DATE(created_at) as day, AVG(ping_ws) as avg_ws, "
            "AVG(ping_rest) as avg_rest, AVG(ping_discord) as avg_discord "
            "FROM ping GROUP BY DATE(created_at) ORDER BY day DESC LIMIT 30"
        )
