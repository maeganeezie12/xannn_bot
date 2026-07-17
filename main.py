import asyncio
import logging
import sys

from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from config import GROUP_CHAT_ID, TOKEN
from database import init_db
from handlers.booking import booking_conv_handler, cancelbooking_command
from handlers.event import cancelevent_command, event_conv_handler
from handlers.general import (
    attendance_callback_handler,
    cancel_booking_handler,
    capture_private_chat,
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
from handlers.plans import cancelplan_conv_handler, cancelplanday_command, myplans_handler, plan_conv_handler
from handlers.travel import (
    canceltrip_handler,
    canceltrip_text_command,
    jointrip_callback,
    jointrip_command,
    travel_conv_handler,
    trips_filter_callback,
    trips_handler,
)
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
    await init_db()
    setup_scheduler(application)

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
    pass


def main():
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()

    # Conversation handlers first (highest priority)
    app.add_handler(event_conv_handler)
    app.add_handler(booking_conv_handler)
    app.add_handler(plan_conv_handler)
    app.add_handler(cancelplan_conv_handler)
    app.add_handler(travel_conv_handler)

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
    app.add_handler(CommandHandler("travel",         travel_conv_handler))
    app.add_handler(CommandHandler("trips",          trips_handler))
    app.add_handler(CommandHandler("jointrip",       jointrip_command))
    app.add_handler(CommandHandler("canceltrip",     canceltrip_handler))

    # Tappable /edit<id> /cancel<id> text commands shown next to items in list views
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/canceltrip\d+$"),    canceltrip_text_command))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/cancelbooking\d+$"), cancelbooking_command))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/cancelevent\d+$"),   cancelevent_command))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^/cancelplan\d{8}$"),  cancelplanday_command))

    # Callback queries
    app.add_handler(CallbackQueryHandler(attendance_callback_handler, pattern=r"^attend_"))
    app.add_handler(CallbackQueryHandler(change_reminders_callback,   pattern=r"^chrem_"))
    app.add_handler(CallbackQueryHandler(jointrip_callback,           pattern=r"^jointrip_"))
    app.add_handler(CallbackQueryHandler(trips_filter_callback,       pattern=r"^trips_"))

    # Runs alongside every other handler (separate group) to remember each
    # family member's private chat ID the first time they DM the bot
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE, capture_private_chat), group=1)

    logger.info("XANNNBot starting...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
