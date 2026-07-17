import logging
from datetime import timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from config import FAMILY, FRIDAY_PROMPT_HOUR, FRIDAY_PROMPT_MINUTE, GROUP_CHAT_ID, TIMEZONE

logger = logging.getLogger(__name__)
SGT = pytz.timezone(TIMEZONE)


async def _send_friday_prompt(bot):
    from database import get_user_chat_id

    unreachable = []
    for username, name in FAMILY.items():
        chat_id = await get_user_chat_id(username)
        if not chat_id:
            unreachable.append(f"@{username}")
            continue
        text = (
            f"Hey {name}! 👋 It's Friday — what are your weekend plans?\n\n"
            "Drop them with /plan so everyone knows what's up!"
        )
        try:
            await bot.send_message(chat_id=chat_id, text=text)
        except Exception as e:
            logger.error("Friday PM to %s failed: %s", username, e)
            unreachable.append(f"@{username}")

    if unreachable and GROUP_CHAT_ID:
        try:
            await bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=(
                    "👋 " + ", ".join(unreachable) + " — I couldn't message you privately for "
                    "the Friday planning reminder. Send me any DM (e.g. /start) once so I can "
                    "reach you directly from now on!"
                ),
            )
        except Exception as e:
            logger.error("Friday prompt fallback failed: %s", e)


async def _send_event_reminder(bot, event_id: int, event_name: str, label: str):
    from database import get_attendance, get_event, is_muted
    from utils import format_date, format_time

    event = await get_event(event_id)
    if not event or event["is_closed"]:
        return

    attendance = await get_attendance(event_id)
    going = [a["username"] for a in attendance if a["status"] in ("going", "maybe")]

    not_muted = [u for u in going if not await is_muted(event_id, u)]

    h, m = map(int, event["time"].split(":"))
    text = (
        f"⏰ Reminder: *{event_name}* is {label}!\n"
        f"📆 {format_date(event['date'])} at {format_time(h, m)}"
    )
    if event.get("location"):
        text += f"\n📍 {event['location']}"
    if not_muted:
        text += "\n\n" + " ".join(f"@{u}" for u in not_muted)

    try:
        await bot.send_message(chat_id=GROUP_CHAT_ID, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error("Event reminder failed (event %s): %s", event_id, e)


def setup_scheduler(application):
    scheduler = AsyncIOScheduler(timezone=SGT)

    scheduler.add_job(
        _send_friday_prompt,
        CronTrigger(day_of_week="fri", hour=FRIDAY_PROMPT_HOUR, minute=FRIDAY_PROMPT_MINUTE, timezone=SGT),
        args=[application.bot],
        id="friday_prompt",
        replace_existing=True,
    )

    scheduler.start()
    application.bot_data["scheduler"] = scheduler
    logger.info("Scheduler started — Friday prompt set for %02d:%02d SGT", FRIDAY_PROMPT_HOUR, FRIDAY_PROMPT_MINUTE)


def schedule_event_reminders(application, event_id: int, event_name: str, event_dt, reminder_24h: bool, reminder_1h: bool):
    from utils import now_sgt

    scheduler = application.bot_data.get("scheduler")
    if not scheduler:
        return

    now = now_sgt()

    if reminder_24h:
        fire = event_dt - timedelta(hours=24)
        if fire > now:
            scheduler.add_job(
                _send_event_reminder,
                DateTrigger(run_date=fire),
                args=[application.bot, event_id, event_name, "tomorrow"],
                id=f"rem24_{event_id}",
                replace_existing=True,
            )

    if reminder_1h:
        fire = event_dt - timedelta(hours=1)
        if fire > now:
            scheduler.add_job(
                _send_event_reminder,
                DateTrigger(run_date=fire),
                args=[application.bot, event_id, event_name, "in 1 hour"],
                id=f"rem1_{event_id}",
                replace_existing=True,
            )


def remove_event_reminders(application, event_id: int):
    scheduler = application.bot_data.get("scheduler")
    if not scheduler:
        return
    for job_id in (f"rem24_{event_id}", f"rem1_{event_id}"):
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass
