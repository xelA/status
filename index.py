import subprocess
import time
import asyncio

from dotenvplus import DotEnv
from datetime import datetime
from postgreslite import PostgresLite
from quart import Quart, render_template, request

from utils import discord

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

config = DotEnv(".env")
app = Quart(__name__)

db = PostgresLite("./storage.db").connect()
xela = discord.xelAAPI(db=db, config=config)  # type: ignore

git_log = subprocess.getoutput('git log -1 --pretty=format:"%h %s" --abbrev-commit').split(" ")
git_rev, git_commit = (git_log[0], " ".join(git_log[1:]))


@app.before_serving
async def _startup():
    xela.update_cache()
    loop.create_task(xela._background_task())  # noqa: RUF006


def unix_timestamp(timestamp: str | datetime) -> float | int:
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
        return time.mktime(
            datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").timetuple()
        )

    if isinstance(timestamp, datetime):
        return time.mktime(timestamp.timetuple())

    return timestamp


@app.route("/")
async def _index():
    reverse_database_xela_cache = xela.cache_data[::-1]

    return await render_template(
        "index.html",
        bot=xela,
        discordstatus=xela.discord.data_status,
        git_rev=git_rev,
        git_commit=git_commit,
        top_stats={
            "WebSocket Ping": f"{xela.ping_ws:,} ms",
            "REST Ping": f"{xela.ping_rest:,} ms",
            "Discord Ping": f"{xela.ping_discord:,} ms",
            "Server Installs": f"{xela.server_installs:,}",
            "User Installs": f"{xela.user_installs:,}",
            "DB Entries": f"{xela.database:,}",
        },
        data=xela.cache_data,
        data_count=len(xela.cache_data),
        lists={
            "ws": [g["ping_ws"] for g in reverse_database_xela_cache],
            "rest": [g["ping_rest"] for g in reverse_database_xela_cache],
            "discord": [g["ping_discord"] for g in reverse_database_xela_cache],
            "timestamps": [
                unix_timestamp(g["created_at"])
                for g in reverse_database_xela_cache
            ],
        }
    )


@app.route("/api")
async def api_all():
    """ Endpoint that returns the latest and history data. """
    payload = {}

    # Check the url parameters
    show = request.args.get("show", "")

    show_spesific = show.split(",")

    if "latest" in show_spesific:
        payload["latest"] = xela.api_latest()

    if "history" in show_spesific:
        payload["history"] = xela.api_history()

    if not payload:
        return {
            "error": "No data to show, please select something...",
        }, 400

    return payload


app.run(
    host=config["HTTP_HOST"],
    port=config["HTTP_PORT"],
    debug=config["HTTP_DEBUG"],
    loop=loop
)
