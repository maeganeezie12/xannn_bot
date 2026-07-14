from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import FAMILY, GROUP_CHAT_ID
from database import (
    create_event,
    delete_event,
    get_attendance,
    get_event,
    update_event,
    update_event_message_id,
    update_event_reminders,
)
from utils import format_date, format_time, get_event_datetime, normalize_username, parse_date, parse_time, remove_keyboard_row

NAME, DATE, TIME, LOCATION, NOTES, REMINDERS = range(6)


# ── Helpers (used by general.py too) ─────────────────────────────────────────

def build_event_card(event_id, name, date_str, time_str, location, notes, attendance_list):
    h, m = map(int, time_str.split(":"))
    lines = [
        f"📅 *{name}* (\\#{event_id})",
        f"📆 {format_date(date_str)} · {format_time(h, m)}",
    ]
    if location:
        lines.append(f"📍 {location}")
    if notes:
        lines.append(f"📝 {notes}")

    going     = [FAMILY.get(a["username"], f"@{a['username']}") for a in attendance_list if a["status"] == "going"]
    not_going = [FAMILY.get(a["username"], f"@{a['username']}") for a in attendance_list if a["status"] == "not_going"]

    lines += [
        "",
        f"✅ Going: {', '.join(going) or '—'}",
        f"❌ Not going: {', '.join(not_going) or '—'}",
    ]
    return "\n".join(lines)


def attendance_keyboard(event_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Going",     callback_data=f"attend_{event_id}_going"),
        InlineKeyboardButton("❌ Not going", callback_data=f"attend_{event_id}_not_going"),
    ]])


# ── Conversation steps ────────────────────────────────────────────────────────

async def event_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if normalize_username(update.effective_user.username) not in FAMILY:
        await update.message.reply_text("You're not in the Tay family group!")
        return ConversationHandler.END
    if not GROUP_CHAT_ID:
        await update.message.reply_text("Bot setup isn't complete yet — GROUP_CHAT_ID missing in .env")
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text("New event! 🎉 What's it called?")
    return NAME


async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text(
        "What date? Say *Saturday*, *Sunday*, or *DD/MM* (e.g. 28/6).",
        parse_mode="Markdown",
    )
    return DATE


async def got_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = parse_date(update.message.text)
    if not d:
        await update.message.reply_text("Couldn't read that — try *Saturday*, *Sunday*, or *28/6*.", parse_mode="Markdown")
        return DATE
    context.user_data["date"] = d.strftime("%Y-%m-%d")
    await update.message.reply_text("What time? e.g. *3pm*, *7:30pm*, *19:30*", parse_mode="Markdown")
    return TIME


async def got_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parsed = parse_time(update.message.text)
    if not parsed:
        await update.message.reply_text("Try *3pm*, *7:30pm*, or *19:30*.", parse_mode="Markdown")
        return TIME
    h, m = parsed
    context.user_data["time"] = f"{h:02d}:{m:02d}"
    await update.message.reply_text("Location? (or *skip*)", parse_mode="Markdown")
    return LOCATION


async def got_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["location"] = None if text.lower() == "skip" else text
    await update.message.reply_text("Any notes? (or *skip*)", parse_mode="Markdown")
    return NOTES


async def got_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["notes"] = None if text.lower() == "skip" else text
    await update.message.reply_text(
        "Send reminders for this event?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("24h before", callback_data="rem_24h"),
             InlineKeyboardButton("1h before",  callback_data="rem_1h")],
            [InlineKeyboardButton("Both",        callback_data="rem_both"),
             InlineKeyboardButton("No reminders", callback_data="rem_none")],
        ]),
    )
    return REMINDERS


async def got_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    choice = query.data
    r24 = choice in ("rem_24h", "rem_both")
    r1  = choice in ("rem_1h",  "rem_both")

    d = context.user_data
    edit_id = d.get("edit_event_id")

    if edit_id:
        await update_event(edit_id, d["name"], d["date"], d["time"], d.get("location"), d.get("notes"))
        await update_event_reminders(edit_id, r24, r1)
        event_id = edit_id
        event = await get_event(event_id)

        if event["event_message_id"] and GROUP_CHAT_ID:
            att  = await get_attendance(event_id)
            card = build_event_card(event_id, d["name"], d["date"], d["time"], d.get("location"), d.get("notes"), att)
            try:
                await context.bot.edit_message_text(
                    chat_id=GROUP_CHAT_ID,
                    message_id=event["event_message_id"],
                    text=card,
                    reply_markup=attendance_keyboard(event_id),
                    parse_mode="Markdown",
                )
            except Exception:
                pass

        from scheduler import remove_event_reminders, schedule_event_reminders
        remove_event_reminders(context.application, event_id)
        if r24 or r1:
            schedule_event_reminders(
                context.application, event_id, d["name"],
                get_event_datetime(d["date"], d["time"]), r24, r1,
            )

        await query.edit_message_text(f"Event #{event_id} updated! 👍")
        return ConversationHandler.END

    event_id = await create_event(
        name=d["name"], date=d["date"], time=d["time"],
        location=d.get("location"), notes=d.get("notes"),
        creator_username=normalize_username(query.from_user.username),
        reminder_24h=r24, reminder_1h=r1,
    )

    card = build_event_card(event_id, d["name"], d["date"], d["time"], d.get("location"), d.get("notes"), [])
    msg = await context.bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=card,
        reply_markup=attendance_keyboard(event_id),
        parse_mode="Markdown",
    )
    await update_event_message_id(event_id, msg.message_id)

    if r24 or r1:
        from scheduler import schedule_event_reminders
        schedule_event_reminders(
            context.application, event_id, d["name"],
            get_event_datetime(d["date"], d["time"]), r24, r1,
        )

    await query.edit_message_text(f"Done! Event #{event_id} posted to the group. 👍")
    return ConversationHandler.END


async def event_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Event creation cancelled.")
    return ConversationHandler.END


async def eventedit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    username = normalize_username(query.from_user.username)
    event_id = int(query.data.split("_")[1])
    event    = await get_event(event_id)

    if not event:
        await query.answer("Event not found.", show_alert=True)
        return ConversationHandler.END
    if event["creator_username"] != username:
        await query.answer("Only the event creator can edit this!", show_alert=True)
        return ConversationHandler.END

    await query.answer()
    context.user_data.clear()
    context.user_data["edit_event_id"] = event_id
    await query.message.reply_text(
        f"Editing *{event['name']}*. What's the new name? (or send the same name)",
        parse_mode="Markdown",
    )
    return NAME


async def eventcancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    username = normalize_username(query.from_user.username)
    event_id = int(query.data.split("_")[1])
    event    = await get_event(event_id)

    if not event:
        await query.answer("Event not found.", show_alert=True)
        return
    if event["creator_username"] != username:
        await query.answer("Only the event creator can cancel this!", show_alert=True)
        return

    await delete_event(event_id)
    await query.answer("Event cancelled.")

    if event["event_message_id"] and GROUP_CHAT_ID:
        try:
            await context.bot.edit_message_text(
                chat_id=GROUP_CHAT_ID,
                message_id=event["event_message_id"],
                text=f"🚫 *{event['name']}* has been cancelled.",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    from scheduler import remove_event_reminders
    remove_event_reminders(context.application, event_id)

    try:
        new_kb = remove_keyboard_row(query.message.reply_markup.inline_keyboard, event_id)
        await query.edit_message_reply_markup(InlineKeyboardMarkup(new_kb))
    except Exception:
        pass


event_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("event", event_start),
        CallbackQueryHandler(eventedit_start, pattern=r"^eventedit_\d+$"),
    ],
    states={
        NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
        DATE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, got_date)],
        TIME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, got_time)],
        LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_location)],
        NOTES:    [MessageHandler(filters.TEXT & ~filters.COMMAND, got_notes)],
        REMINDERS:[CallbackQueryHandler(got_reminders, pattern="^rem_")],
    },
    fallbacks=[CommandHandler("cancel", event_cancel)],
    allow_reentry=True,
    per_message=False,
)
