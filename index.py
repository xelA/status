import subprocess
import time
import asyncio

from dotenvplus import DotEnv
from typing import Union
from datetime import datetime
from postgreslite import PostgresLite
from quart import Quart, render_template

from utils import discord

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

config = DotEnv(".env")
app = Quart(__name__)

db = PostgresLite("./storage.db").connect()
xela = discord.xelAAPI(db=db, config=config)

git_log = subprocess.getoutput('git log -1 --pretty=format:"%h %s" --abbrev-commit').split(" ")
git_rev, git_commit = (git_log[0], " ".join(git_log[1:]))


@app.before_serving
async def startup():
    xela.update_cache()
    loop.create_task(xela._background_task())


def unix_timestamp(timestamp: Union[str, datetime]) -> int:
    if isinstance(timestamp, str):
        return time.mktime(
            datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").timetuple()
        )
    elif isinstance(timestamp, datetime):
        return time.mktime(timestamp.timetuple())
    else:
        return timestamp


@app.route("/")
async def index():
    reverse_database_xela_cache = xela.cache_data[::-1]

    return await render_template(
        "index.html",
        bot=xela,
        discordstatus=xela.discord.current_status(),
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


@app.route("/api/history")
async def index_json():
    return {
        "latest": {
            "discord_status": xela.discord.current_status(),
            "ping_ws": xela.ping_ws,
            "ping_rest": xela.ping_rest,
            "ping_discord": xela.ping_discord,
            "server_installs": xela.server_installs,
            "user_installs": xela.user_installs,
        },
        "history": [
            {
                "server_installs": g["server_installs"],
                "user_installs": g["user_installs"],
                "ping_ws": g["ping_ws"],
                "ping_discord": g["ping_discord"],
                "ping_rest": g["ping_rest"],
                "created_at": g["created_at"],  # Ensure it's ISO format
            }
            for g in xela.cache_data
        ],
    }


app.run(
    host=config["HTTP_HOST"],
    port=config["HTTP_PORT"],
    debug=config["HTTP_DEBUG"],
    loop=loop
)
