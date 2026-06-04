import asyncio
import logging
import subprocess

from aiohttp import web
from dotenvplus import DotEnv

from postgreslite import PostgresLite

from utils import discord, default

default.setup_logging()
_log = logging.getLogger("xela_status")

config = DotEnv(".env")

db = PostgresLite("./storage.db").connect()

columns = db.fetch("PRAGMA table_info(ping)")
if not any(col["name"] == "users" for col in columns):
    db.execute("ALTER TABLE ping ADD COLUMN users BIGINT DEFAULT 0")

xela = discord.xelAAPI(db=db, config=config)  # type: ignore

git_log = subprocess.getoutput('git log -1 --pretty=format:"%h %s" --abbrev-commit').split(" ")
git_rev, git_commit = (git_log[0], " ".join(git_log[1:]))


async def _index(_request: web.Request) -> web.Response:
    reverse_database_xela_cache = xela.cache_data[::-1]

    return default.html_response(
        "index.html",
        bot=xela,
        discordstatus=xela.discord.data_status,
        git_rev=git_rev,
        git_commit=git_commit,
        data=xela.cache_data,
        viewable_users=f"{xela.users:,}",
        data_count=len(xela.cache_data),
        lists={
            "ws": [g["ping_ws"] for g in reverse_database_xela_cache],
            "rest": [g["ping_rest"] for g in reverse_database_xela_cache],
            "discord": [g["ping_discord"] for g in reverse_database_xela_cache],
            "users": [g.get("users", 0) for g in reverse_database_xela_cache],
            "timestamps": [
                default.unix_timestamp(g["created_at"])
                for g in reverse_database_xela_cache
            ],
        },
        daily_lists={
            "ws": [round(g["avg_ws"]) for g in reversed(xela.daily_cache_data)],
            "rest": [round(g["avg_rest"]) for g in reversed(xela.daily_cache_data)],
            "discord": [round(g["avg_discord"]) for g in reversed(xela.daily_cache_data)],
            "days": [g["day"] for g in reversed(xela.daily_cache_data)],
        }
    )


async def _api(request: web.Request) -> web.Response:
    """ Endpoint that returns the latest and history data. """
    payload = {}

    show = request.rel_url.query.get("show", "")
    show_specific = show.split(",")

    if "latest" in show_specific:
        payload["latest"] = xela.api_latest()

    if "history" in show_specific:
        payload["history"] = xela.api_history()

    if "user" in show_specific:
        payload["user"] = xela.api_user()

    if "daily" in show_specific:
        payload["daily"] = xela.api_daily()

    if not payload:
        return default.json_response(
            {"error": "No data to show, please select something..."},
            status=400
        )

    return default.json_response(payload)


@web.middleware
async def _log_requests(request: web.Request, handler) -> web.Response:
    response = await handler(request)
    _log.info(f"{request.method} {request.path} ({response.status})")
    return response


async def _background_ctx(_app: web.Application):
    xela.update_cache()
    task = asyncio.create_task(xela._background_task())
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


app = web.Application(middlewares=[_log_requests])
app.router.add_get("/", _index)
app.router.add_get("/api", _api)
app.router.add_static("/static", "static")
app.cleanup_ctx.append(_background_ctx)

web.run_app(
    app,
    host=config["HTTP_HOST"],
    port=int(config["HTTP_PORT"]),
)
