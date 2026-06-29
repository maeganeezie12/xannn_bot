from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import BOOKING_BUFFER_MINUTES, FAMILY, GROUP_CHAT_ID, SPACES
from database import create_booking, get_bookings_for_space_date
from utils import format_date, format_time, normalize_username, parse_date, parse_time, times_overlap

SPACE, DATE, START_TIME, END_TIME, NOTE = range(5)


async def book_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if normalize_username(update.effective_user.username) not in FAMILY:
        await update.message.reply_text("You're not in the Tay family group!")
        return ConversationHandler.END
    if not GROUP_CHAT_ID:
        await update.message.reply_text("Bot setup isn't complete yet — GROUP_CHAT_ID missing in .env")
        return ConversationHandler.END

    context.user_data.clear()
    keyboard = [[InlineKeyboardButton(s, callback_data=f"space_{s}")] for s in SPACES]
    await update.message.reply_text("Which shared space/asset do you want to book?", reply_markup=InlineKeyboardMarkup(keyboard))
    return SPACE


async def got_space(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["space"] = query.data[len("space_"):]
    await query.edit_message_text(
        f"*{context.user_data['space']}* — what date? (*Saturday*, *Sunday*, or *DD/MM*)",
        parse_mode="Markdown",
    )
    return DATE


async def got_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = parse_date(update.message.text)
    if not d:
        await update.message.reply_text("Couldn't read that — try *Saturday*, *Sunday*, or *28/6*.", parse_mode="Markdown")
        return DATE
    context.user_data["date"] = d.strftime("%Y-%m-%d")
    await update.message.reply_text("Start time? (e.g. *3pm*, *15:00*)", parse_mode="Markdown")
    return START_TIME


async def got_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parsed = parse_time(update.message.text)
    if not parsed:
        await update.message.reply_text("Try *3pm*, *3:30pm*, or *15:00*.", parse_mode="Markdown")
        return START_TIME
    h, m = parsed
    context.user_data["start_time"] = f"{h:02d}:{m:02d}"
    await update.message.reply_text("End time?")
    return END_TIME


async def got_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parsed = parse_time(update.message.text)
    if not parsed:
        await update.message.reply_text("Try *3pm*, *3:30pm*, or *15:00*.", parse_mode="Markdown")
        return END_TIME

    h, m = parsed
    end_time = f"{h:02d}:{m:02d}"
    start_time = context.user_data["start_time"]

    if end_time <= start_time:
        await update.message.reply_text("End time must be after start time. Try again.")
        return END_TIME

    context.user_data["end_time"] = end_time
    await update.message.reply_text(
        "Quick note for the family? (e.g. 'hosting Priya and friends') — or *skip*",
        parse_mode="Markdown",
    )
    return NOTE


async def got_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    note = None if text.lower() == "skip" else text

    d = context.user_data
    space = d["space"]
    date  = d["date"]
    start = d["start_time"]
    end   = d["end_time"]
    username = normalize_username(update.effective_user.username)

    existing = await get_bookings_for_space_date(space, date)
    for b in existing:
        if times_overlap(start, end, b["start_time"], b["end_time"], BOOKING_BUFFER_MINUTES):
            blocker = FAMILY.get(b["creator_username"], f"@{b['creator_username']}")
            sh, sm = map(int, b["start_time"].split(":"))
            eh, em = map(int, b["end_time"].split(":"))
            await update.message.reply_text(
                f"🚫 Can't book — {blocker} already has *{b['space']}* on {format_date(date)} "
                f"from {format_time(sh, sm)} to {format_time(eh, em)} "
                f"(including {BOOKING_BUFFER_MINUTES} min buffer).\n\nPick a different time or space.",
                parse_mode="Markdown",
            )
            return ConversationHandler.END

    booking_id = await create_booking(space, date, start, end, note, username)

    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    name = FAMILY.get(username, f"@{username}")
    note_txt = f' ("{note}")' if note else ""

    await context.bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=(
            f"🏠 *{name}* has booked *{space}* on {format_date(date)}, "
            f"{format_time(sh, sm)}–{format_time(eh, em)}{note_txt}.\n"
            f"Booking ID: \\#{booking_id}"
        ),
        parse_mode="Markdown",
    )
    await update.message.reply_text(f"Booked! 🎉 Booking ID: #{booking_id}")
    return ConversationHandler.END


async def book_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Booking cancelled.")
    return ConversationHandler.END


booking_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("book", book_start)],
    states={
        SPACE:      [CallbackQueryHandler(got_space,      pattern="^space_")],
        DATE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, got_date)],
        START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_start_time)],
        END_TIME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, got_end_time)],
        NOTE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, got_note)],
    },
    fallbacks=[CommandHandler("cancel", book_cancel)],
    allow_reentry=True,
)
