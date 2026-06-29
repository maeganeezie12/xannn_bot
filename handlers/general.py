from collections import defaultdict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import FAMILY, GROUP_CHAT_ID
from database import (
    close_event,
    delete_booking,
    get_attendance,
    get_booking,
    get_event,
    get_plans_for_dates,
    get_upcoming_bookings,
    get_upcoming_events,
    get_weekend_bookings,
    mute_reminder,
    set_attendance,
    update_event_reminders,
)
import io
from handlers.event import attendance_keyboard, build_event_card
from utils import format_date, format_time, generate_ics, get_weekend_dates, normalize_username


# ── /weekend ──────────────────────────────────────────────────────────────────

async def weekend_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sat, sun = get_weekend_dates()
    sat_str, sun_str = str(sat), str(sun)

    events   = await get_upcoming_events()
    weekend_events = [e for e in events if e["date"] in (sat_str, sun_str)]

    plans    = await get_plans_for_dates([sat_str, sun_str])
    by_user_date = {}
    for p in plans:
        by_user_date.setdefault(p["username"], {})[p["date"]] = p["plan_text"]

    bookings = await get_weekend_bookings(sat_str, sun_str)

    lines = [f"🗓 *Weekend of {format_date(sat_str)} – {format_date(sun_str)}*\n"]

    if weekend_events:
        lines.append("*EVENTS*")
        for e in weekend_events:
            h, m = map(int, e["time"].split(":"))
            att   = await get_attendance(e["id"])
            going = [FAMILY.get(a["username"], f"@{a['username']}") for a in att if a["status"] == "going"]
            stats = ", ".join(going) if going else "no responses yet"
            day   = "Sat" if e["date"] == sat_str else "Sun"
            lines.append(f"• {day} {format_time(h, m)} – {e['name']} ({stats})")
        lines.append("")

    lines.append("*PLANS*")
    for username, name in FAMILY.items():
        user_plans = by_user_date.get(username, {})
        sat_plan = user_plans.get(sat_str)
        sun_plan = user_plans.get(sun_str)
        if sat_plan or sun_plan:
            sat_txt = sat_plan or "—"
            sun_txt = sun_plan or "—"
            lines.append(f"*{name}*: Sat: {sat_txt} | Sun: {sun_txt}")
        else:
            lines.append(f"*{name}*: hasn't shared yet ⏳")

    if bookings:
        lines.append("\n*🏠 ASSET BOOKINGS*")
        for b in bookings:
            sh, sm = map(int, b["start_time"].split(":"))
            eh, em = map(int, b["end_time"].split(":"))
            day    = "Sat" if b["date"] == sat_str else "Sun"
            booker = FAMILY.get(b["creator_username"], f"@{b['creator_username']}")
            note   = f' — "{b["note"]}"' if b["note"] else ""
            lines.append(f"• {day} {format_time(sh, sm)}–{format_time(eh, em)}: {b['space']} ({booker}{note})")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /events ───────────────────────────────────────────────────────────────────

async def events_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    events = await get_upcoming_events()

    if not events:
        await update.message.reply_text("No upcoming events. Create one with /event!")
        return

    by_date = defaultdict(list)
    for e in events:
        by_date[e["date"]].append(e)

    lines = ["*Upcoming Events*\n"]
    for date in sorted(by_date):
        lines.append(f"*{format_date(date)}*")
        for e in by_date[date]:
            h, m = map(int, e["time"].split(":"))
            att   = await get_attendance(e["id"])
            going = [FAMILY.get(a["username"], f"@{a['username']}") for a in att if a["status"] == "going"]
            not_going = [FAMILY.get(a["username"], f"@{a['username']}") for a in att if a["status"] == "not_going"]
            loc   = f" @ {e['location']}" if e.get("location") else ""
            going_txt = f"✅ {', '.join(going)}" if going else ""
            not_going_txt = f"❌ {', '.join(not_going)}" if not_going else ""
            attendance_txt = "  |  ".join(filter(None, [going_txt, not_going_txt])) or "No responses yet"
            lines.append(f"  *#{e['id']}* {format_time(h, m)} — {e['name']}{loc}")
            lines.append(f"  {attendance_txt}")
        lines.append("")

    await update.message.reply_text("\n".join(lines).strip(), parse_mode="Markdown")


# ── /status ───────────────────────────────────────────────────────────────────

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sat, sun = get_weekend_dates()
    sat_str, sun_str = str(sat), str(sun)
    plans = await get_plans_for_dates([sat_str, sun_str])
    submitted = {p["username"] for p in plans}

    lines   = [f"*Weekend plan status — {format_date(str(sat))}*\n"]
    pending = []
    for username, name in FAMILY.items():
        if username in submitted:
            lines.append(f"✅ {name}")
        else:
            lines.append(f"⏳ {name}")
            pending.append(f"@{username}")

    if pending:
        lines.append(f"\nHey {', '.join(pending)} — share your plans with /plan! 👀")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /spaces ───────────────────────────────────────────────────────────────────

async def spaces_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bookings = await get_upcoming_bookings()

    if not bookings:
        await update.message.reply_text("No space/asset bookings coming up — all clear! 🟢")
        return

    by_date = defaultdict(list)
    for b in bookings:
        by_date[b["date"]].append(b)

    lines = ["*Upcoming space/asset bookings:*\n"]
    for date in sorted(by_date):
        lines.append(f"*{format_date(date)}*")
        for b in by_date[date]:
            sh, sm = map(int, b["start_time"].split(":"))
            eh, em = map(int, b["end_time"].split(":"))
            booker = FAMILY.get(b["creator_username"], f"@{b['creator_username']}")
            note   = f' "{b["note"]}"' if b["note"] else ""
            lines.append(f"  • \\#{b['id']} {b['space']}: {format_time(sh, sm)}–{format_time(eh, em)} ({booker}{note})")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /help / /start ────────────────────────────────────────────────────────────

async def whoami_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.effective_user.username
    normalized = normalize_username(raw)
    name = FAMILY.get(normalized)
    if name:
        await update.message.reply_text(f"You're *{name}* (`@{normalized}`) — you're in the family list ✅", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"Your Telegram username is `@{normalized or '(none set)'}` — not in the family list ❌\n\n"
            f"Tell Maegan your exact username so she can add you.",
            parse_mode="Markdown",
        )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*XANNNBot* — Tay family weekend planner 🏡\n\n"
        "/plan — Share plans for any day \\(weekday or weekend\\)\n"
        "/cancelplan — Remove plans for a specific day\n"
        "/myplans — See all your upcoming saved plans\n"
        "/weekend — See the full weekend summary\n"
        "/status — See who's shared their weekend plans\n"
        "/seeevents — See all upcoming events\n"
        "/event — Create a new event with attendance poll\n"
        "/book — Book a shared space/asset \\(room, car, etc\\)\n"
        "/spaces — See all upcoming space/asset bookings\n"
        "/cancel\\_booking \\[id\\] — Cancel your booking\n"
        "/close\\_poll \\[id\\] — Close an event's attendance poll\n"
        "/reminders \\[id\\] — Change reminder settings \\(creator only\\)\n"
        "/mute \\[id\\] — Mute reminders for yourself on an event\n"
        "/cancel — Cancel current wizard"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


# ── /close_poll ───────────────────────────────────────────────────────────────

async def close_poll_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = normalize_username(update.effective_user.username)
    args = context.args

    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /close_poll [event_id]")
        return

    event_id = int(args[0])
    event = await get_event(event_id)
    if not event:
        await update.message.reply_text(f"No event with ID #{event_id}.")
        return
    if event["creator_username"] != username:
        await update.message.reply_text("Only the event creator can close the poll.")
        return

    await close_event(event_id)

    if event["event_message_id"] and GROUP_CHAT_ID:
        att  = await get_attendance(event_id)
        text = build_event_card(
            event_id, event["name"], event["date"], event["time"],
            event.get("location"), event.get("notes"), att,
        ) + "\n\n_Poll closed_"
        try:
            await context.bot.edit_message_text(
                chat_id=GROUP_CHAT_ID,
                message_id=event["event_message_id"],
                text=text,
                parse_mode="Markdown",
            )
        except Exception:
            pass

    await update.message.reply_text(f"Poll for *{event['name']}* closed.", parse_mode="Markdown")


# ── /cancel_booking ───────────────────────────────────────────────────────────

async def cancel_booking_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = normalize_username(update.effective_user.username)
    args = context.args

    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /cancel_booking [booking_id]")
        return

    booking_id = int(args[0])
    booking = await get_booking(booking_id)
    if not booking:
        await update.message.reply_text(f"No booking with ID #{booking_id}.")
        return
    if booking["creator_username"] != username:
        await update.message.reply_text("You can only cancel your own bookings.")
        return

    await delete_booking(booking_id)

    sh, sm = map(int, booking["start_time"].split(":"))
    eh, em = map(int, booking["end_time"].split(":"))
    name = FAMILY.get(username, f"@{username}")

    if GROUP_CHAT_ID:
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=(
                f"🔓 *{name}* cancelled their booking of *{booking['space']}* on "
                f"{format_date(booking['date'])}, {format_time(sh, sm)}–{format_time(eh, em)}. "
                f"Space is free again!"
            ),
            parse_mode="Markdown",
        )
    await update.message.reply_text("Booking cancelled. The group has been notified.")


# ── /mute ─────────────────────────────────────────────────────────────────────

async def mute_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = normalize_username(update.effective_user.username)
    args = context.args

    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /mute [event_id]")
        return

    event_id = int(args[0])
    event = await get_event(event_id)
    if not event:
        await update.message.reply_text(f"No event with ID #{event_id}.")
        return

    await mute_reminder(event_id, username)
    await update.message.reply_text(f"Muted reminders for *{event['name']}* for yourself.", parse_mode="Markdown")


# ── /reminders ────────────────────────────────────────────────────────────────

async def reminders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = normalize_username(update.effective_user.username)
    args = context.args

    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /reminders [event_id]")
        return

    event_id = int(args[0])
    event = await get_event(event_id)
    if not event:
        await update.message.reply_text(f"No event with ID #{event_id}.")
        return
    if event["creator_username"] != username:
        await update.message.reply_text("Only the event creator can change reminder settings.")
        return

    await update.message.reply_text(
        f"Change reminders for *{event['name']}*:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("24h before",   callback_data=f"chrem_{event_id}_24h"),
             InlineKeyboardButton("1h before",    callback_data=f"chrem_{event_id}_1h")],
            [InlineKeyboardButton("Both",          callback_data=f"chrem_{event_id}_both"),
             InlineKeyboardButton("No reminders",  callback_data=f"chrem_{event_id}_none")],
        ]),
        parse_mode="Markdown",
    )


async def change_reminders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, event_id_str, choice = query.data.split("_", 2)
    event_id = int(event_id_str)

    r24 = choice in ("24h", "both")
    r1  = choice in ("1h",  "both")

    await update_event_reminders(event_id, r24, r1)

    event = await get_event(event_id)
    if event:
        from scheduler import remove_event_reminders, schedule_event_reminders
        from utils import get_event_datetime
        remove_event_reminders(context.application, event_id)
        if r24 or r1:
            schedule_event_reminders(
                context.application, event_id, event["name"],
                get_event_datetime(event["date"], event["time"]), r24, r1,
            )

    labels = {"24h": "24h before", "1h": "1h before", "both": "both", "none": "none"}
    await query.edit_message_text(f"Reminders updated: {labels.get(choice, choice)}")


# ── Attendance callback ───────────────────────────────────────────────────────

async def attendance_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    username = normalize_username(query.from_user.username)

    if not username or username not in FAMILY:
        await query.answer("You're not in the Tay family!", show_alert=True)
        return

    await query.answer()

    _, event_id_str, status = query.data.split("_", 2)
    event_id = int(event_id_str)

    event = await get_event(event_id)
    if not event:
        await query.answer("Event not found.", show_alert=True)
        return
    if event["is_closed"]:
        await query.answer("This poll is already closed.", show_alert=True)
        return

    await set_attendance(event_id, username, status)

    att  = await get_attendance(event_id)
    text = build_event_card(
        event_id, event["name"], event["date"], event["time"],
        event.get("location"), event.get("notes"), att,
    )
    try:
        await query.edit_message_text(text=text, reply_markup=attendance_keyboard(event_id), parse_mode="Markdown")
    except Exception:
        pass

    if status == "going":
        try:
            ics = generate_ics(
                event["name"], event["date"], event["time"],
                event.get("location"), event.get("notes"),
            )
            safe_name = event["name"].replace(" ", "_")
            await context.bot.send_document(
                chat_id=query.from_user.id,
                document=io.BytesIO(ics),
                filename=f"{safe_name}.ics",
                caption=f"📅 Tap to add *{event['name']}* to your calendar!",
                parse_mode="Markdown",
            )
        except Exception:
            pass
