import argparse
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

parser = argparse.ArgumentParser(description="xelA status page")
parser.add_argument(
    "--fake-discord-error", nargs="?", const="major", choices=("minor", "major", "critical"),
    metavar="IMPACT", help="Dev: pretend Discord has an incident (minor, major or critical, default major)"
)
# parse_known_args since PM2 passes along extra flags (-u)
args, _ = parser.parse_known_args()

db = PostgresLite("./storage.db").connect()

columns = db.fetch("PRAGMA table_info(ping)")
if not any(col["name"] == "users" for col in columns):
    db.execute("ALTER TABLE ping ADD COLUMN users BIGINT DEFAULT 0")

xela = discord.xelAAPI(db=db, config=config, fake_discord_impact=args.fake_discord_error)  # type: ignore
if args.fake_discord_error:
    _log.warning(f"Faking a {args.fake_discord_error} Discord incident")

git_log = subprocess.getoutput('git log -1 --pretty=format:"%h %s" --abbrev-commit').split(" ")
git_rev, git_commit = (git_log[0], " ".join(git_log[1:]))


def _avg(values: list) -> int:
    return round(sum(values) / len(values)) if values else 0


async def _index(_request: web.Request) -> web.Response:
    reverse_database_xela_cache = xela.cache_data[::-1]
    window = xela.window_cache_data

    return default.html_response(
        "index.html",
        bot=xela,
        discordstatus=xela.discord.data_status,
        git_rev=git_rev,
        git_commit=git_commit,
        server_installs=f"{xela.server_installs:,}",
        user_installs=f"{xela.user_installs:,}",
        viewable_users=f"{xela.users:,}",
        avg_users_server=f"{round(xela.avg_users_server):,}",
        latest={
            "ws": xela.ping_ws,
            "rest": xela.ping_rest,
            "discord": xela.ping_discord,
        },
        avg_24h={
            "ws": _avg([g["avg_ws"] for g in window]),
            "rest": _avg([g["avg_rest"] for g in window]),
            "discord": _avg([g["avg_discord"] for g in window]),
        },
        lists={
            "ws": [g["ping_ws"] for g in reverse_database_xela_cache],
            "rest": [g["ping_rest"] for g in reverse_database_xela_cache],
            "discord": [g["ping_discord"] for g in reverse_database_xela_cache],
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
        },
        window_lists={
            "ws": [round(g["avg_ws"]) for g in xela.window_cache_data],
            "rest": [round(g["avg_rest"]) for g in xela.window_cache_data],
            "discord": [round(g["avg_discord"]) for g in xela.window_cache_data],
            "timestamps": [default.unix_timestamp(g["bucket"]) for g in xela.window_cache_data],
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

    if "window" in show_specific:
        payload["window"] = xela.api_window()

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


async def main():
    """ I only wrapped it in this to make CTRL+C better... """
    runner = web.AppRunner(app, shutdown_timeout=3.0)
    await runner.setup()
    site = web.TCPSite(runner, config["HTTP_HOST"], int(config["HTTP_PORT"]))
    await site.start()
    _log.info(f"Running on http://{config['HTTP_HOST']}:{config['HTTP_PORT']}")
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
