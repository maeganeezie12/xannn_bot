import asyncio
import logging
import sys

from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler

from config import GROUP_CHAT_ID, ICS_DIR, SERVER_PORT, SERVER_URL, TOKEN
from database import init_db
from handlers.booking import booking_conv_handler
from handlers.event import event_conv_handler
from handlers.general import (
    attendance_callback_handler,
    cancel_booking_handler,
    change_reminders_callback,
    close_poll_handler,
    events_handler,
    help_handler,
    mute_handler,
    reminders_handler,
    spaces_handler,
    status_handler,
    weekend_handler,
    whoami_handler,
)
from handlers.plans import cancelplan_conv_handler, myplans_handler, plan_conv_handler
from scheduler import setup_scheduler

# Windows asyncio fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("xannn.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


async def post_init(application):
    import os
    await init_db()
    setup_scheduler(application)

    if SERVER_URL:
        from aiohttp import web
        os.makedirs(ICS_DIR, exist_ok=True)

        async def serve_ics(request):
            filename = request.match_info["filename"]
            if ".." in filename or "/" in filename or "\\" in filename:
                raise web.HTTPNotFound()
            filepath = os.path.join(ICS_DIR, filename)
            if not os.path.isfile(filepath):
                raise web.HTTPNotFound()
            return web.FileResponse(filepath, headers={
                "Content-Type": "text/calendar; charset=utf-8",
                "Content-Disposition": f'inline; filename="{filename}"',
            })

        aio_app = web.Application()
        aio_app.router.add_get("/ics/{filename}", serve_ics)
        runner = web.AppRunner(aio_app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", SERVER_PORT).start()
        application.bot_data["http_runner"] = runner
        logger.info("ICS file server running on port %s", SERVER_PORT)

    if not GROUP_CHAT_ID:
        logger.warning(
            "GROUP_CHAT_ID is not set in .env!\n"
            "  1. Add XANNNBot to your family group chat\n"
            "  2. Send a message in the group\n"
            "  3. Run:  python get_chat_id.py\n"
            "  4. Paste the ID into .env as GROUP_CHAT_ID=<id>\n"
            "  5. Restart the bot"
        )
    else:
        logger.info("Bot ready — group chat ID: %s", GROUP_CHAT_ID)


async def post_shutdown(application):
    runner = application.bot_data.get("http_runner")
    if runner:
        await runner.cleanup()


def main():
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()

    # Conversation handlers first (highest priority)
    app.add_handler(event_conv_handler)
    app.add_handler(booking_conv_handler)
    app.add_handler(plan_conv_handler)
    app.add_handler(cancelplan_conv_handler)

    # Simple commands
    app.add_handler(CommandHandler("start",          help_handler))
    app.add_handler(CommandHandler("whoami",         whoami_handler))
    app.add_handler(CommandHandler("help",           help_handler))
    app.add_handler(CommandHandler("weekend",        weekend_handler))
    app.add_handler(CommandHandler("seeevents",      events_handler))
    app.add_handler(CommandHandler("status",         status_handler))
    app.add_handler(CommandHandler("spaces",         spaces_handler))
    app.add_handler(CommandHandler("close_poll",     close_poll_handler))
    app.add_handler(CommandHandler("cancel_booking", cancel_booking_handler))
    app.add_handler(CommandHandler("mute",           mute_handler))
    app.add_handler(CommandHandler("myplans",        myplans_handler))
    app.add_handler(CommandHandler("reminders",      reminders_handler))

    # Callback queries
    app.add_handler(CallbackQueryHandler(attendance_callback_handler, pattern=r"^attend_"))
    app.add_handler(CallbackQueryHandler(change_reminders_callback,   pattern=r"^chrem_"))

    logger.info("XANNNBot starting...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
