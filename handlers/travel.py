import logging
from datetime import date as date_type

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
    add_trip_companion,
    create_trip,
    delete_trip,
    get_trip,
    get_trip_companions,
    get_upcoming_trips,
)
from utils import format_date, normalize_username, parse_date

logger = logging.getLogger(__name__)

DESTINATION, DEPART_DATE, RETURN_DATE, NOTES, COMPANIONS = range(5)


async def travel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = normalize_username(update.effective_user.username)
    if username not in FAMILY:
        await update.message.reply_text("You're not in the Tay family!")
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text("Where are you going? (destination)")
    return DESTINATION


async def travel_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["destination"] = update.message.text.strip()
    await update.message.reply_text("Departure date? (e.g. 5 Jul, tomorrow, Sat)")
    return DEPART_DATE


async def travel_depart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = parse_date(update.message.text)
    if not d:
        await update.message.reply_text("Couldn't read that date. Try: 5 Jul, 05/07, Saturday")
        return DEPART_DATE
    context.user_data["depart_date"] = str(d)
    await update.message.reply_text("Return date?")
    return RETURN_DATE


async def travel_return(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = parse_date(update.message.text)
    if not d:
        await update.message.reply_text("Couldn't read that date. Try: 5 Jul, 05/07, Saturday")
        return RETURN_DATE
    depart = date_type.fromisoformat(context.user_data["depart_date"])
    if d < depart:
        await update.message.reply_text("Return date must be on or after departure. Try again.")
        return RETURN_DATE
    context.user_data["return_date"] = str(d)
    await update.message.reply_text(
        "Any notes? (e.g. flight details, hotel) — or /skip"
    )
    return NOTES


async def travel_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["notes"] = update.message.text.strip()
    return await _ask_companions(update, context)


async def travel_skip_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["notes"] = None
    return await _ask_companions(update, context)


async def _ask_companions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Open to family members joining you?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Yes, post to group ✈️", callback_data="travelcomp_yes"),
            InlineKeyboardButton("No, just me",           callback_data="travelcomp_no"),
        ]]),
    )
    return COMPANIONS


async def travel_companions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    username = normalize_username(query.from_user.username)
    open_to  = query.data == "travelcomp_yes"

    trip_id = await create_trip(
        username,
        context.user_data["destination"],
        context.user_data["depart_date"],
        context.user_data["return_date"],
        context.user_data.get("notes"),
        open_to,
    )

    name = FAMILY.get(username, f"@{username}")
    dest = context.user_data["destination"]
    dep  = format_date(context.user_data["depart_date"])
    ret  = format_date(context.user_data["return_date"])

    await query.edit_message_text(f"Trip saved! ✈️ {dest}, {dep} → {ret}")

    if open_to and GROUP_CHAT_ID:
        notes_line = f"\n📝 {context.user_data['notes']}" if context.user_data.get("notes") else ""
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=(
                f"✈️ *{name}* is heading to *{dest}*\n"
                f"📅 {dep} → {ret}{notes_line}\n\n"
                f"Anyone want to join?"
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Join this trip ✈️", callback_data=f"jointrip_{trip_id}")
            ]]),
            parse_mode="Markdown",
        )

    return ConversationHandler.END


async def trips_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trips = await get_upcoming_trips()
    if not trips:
        await update.message.reply_text("No upcoming family trips. Plan one with /travel!")
        return

    lines = ["✈️ *Upcoming Family Trips*\n"]
    for t in trips:
        name       = FAMILY.get(t["username"], f"@{t['username']}")
        companions = await get_trip_companions(t["id"])
        comp_names = [FAMILY.get(c["username"], f"@{c['username']}") for c in companions]
        notes_txt  = f"\n  📝 {t['notes']}" if t.get("notes") else ""
        if comp_names:
            comp_txt = f"\n  🧳 Joined by: {', '.join(comp_names)}"
        elif t["open_to_companions"]:
            comp_txt = f"\n  _Open to companions — /jointrip {t['id']}_"
        else:
            comp_txt = ""
        lines.append(
            f"*{name}* → *{t['destination']}* (#{t['id']})\n"
            f"  {format_date(t['depart_date'])} → {format_date(t['return_date'])}"
            f"{notes_txt}{comp_txt}"
        )
        lines.append("")

    await update.message.reply_text("\n".join(lines).strip(), parse_mode="Markdown")


async def jointrip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = normalize_username(update.effective_user.username)
    if username not in FAMILY:
        await update.message.reply_text("You're not in the Tay family!")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /jointrip [trip_id]\nSee IDs with /trips")
        return
    await _do_join(update, context, username, int(context.args[0]))


async def jointrip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    username = normalize_username(query.from_user.username)
    if username not in FAMILY:
        await query.answer("You're not in the Tay family!", show_alert=True)
        return
    await query.answer()
    trip_id = int(query.data.split("_")[1])
    trip    = await get_trip(trip_id)
    if not trip:
        await query.answer("Trip not found.", show_alert=True)
        return
    if trip["username"] == username:
        await query.answer("That's your own trip!", show_alert=True)
        return

    companions = await get_trip_companions(trip_id)
    if any(c["username"] == username for c in companions):
        await query.answer("You've already joined this trip!", show_alert=True)
        return

    await add_trip_companion(trip_id, username)
    companions = await get_trip_companions(trip_id)
    comp_names = [FAMILY.get(c["username"], f"@{c['username']}") for c in companions]

    owner_name = FAMILY.get(trip["username"], f"@{trip['username']}")
    name       = FAMILY.get(username, f"@{username}")
    dep        = format_date(trip["depart_date"])
    ret        = format_date(trip["return_date"])
    notes_line = f"\n📝 {trip['notes']}" if trip.get("notes") else ""

    try:
        await query.edit_message_text(
            text=(
                f"✈️ *{owner_name}* is heading to *{trip['destination']}*\n"
                f"📅 {dep} → {ret}{notes_line}\n\n"
                f"🧳 Joining: {', '.join(comp_names)}"
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Join this trip ✈️", callback_data=f"jointrip_{trip_id}")
            ]]),
            parse_mode="Markdown",
        )
    except Exception:
        pass

    if GROUP_CHAT_ID:
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=f"✈️ *{name}* is joining *{owner_name}*'s trip to *{trip['destination']}*!",
            parse_mode="Markdown",
        )


async def _do_join(update, context, username, trip_id):
    trip = await get_trip(trip_id)
    if not trip:
        await update.message.reply_text(f"No trip #{trip_id} found.")
        return
    if trip["username"] == username:
        await update.message.reply_text("That's your own trip!")
        return
    companions = await get_trip_companions(trip_id)
    if any(c["username"] == username for c in companions):
        await update.message.reply_text("You've already joined this trip!")
        return

    await add_trip_companion(trip_id, username)
    name       = FAMILY.get(username, f"@{username}")
    owner_name = FAMILY.get(trip["username"], f"@{trip['username']}")

    if GROUP_CHAT_ID:
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=f"✈️ *{name}* is joining *{owner_name}*'s trip to *{trip['destination']}*!",
            parse_mode="Markdown",
        )
    await update.message.reply_text(
        f"Done! You're joining {owner_name}'s trip to {trip['destination']}."
    )


async def canceltrip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = normalize_username(update.effective_user.username)
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /canceltrip [trip_id]\nSee IDs with /trips")
        return
    trip_id = int(context.args[0])
    trip    = await get_trip(trip_id)
    if not trip:
        await update.message.reply_text(f"No trip #{trip_id} found.")
        return
    if trip["username"] != username:
        await update.message.reply_text("You can only cancel your own trips.")
        return

    await delete_trip(trip_id)
    name = FAMILY.get(username, f"@{username}")
    if GROUP_CHAT_ID:
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=f"✈️ *{name}*'s trip to *{trip['destination']}* has been cancelled.",
            parse_mode="Markdown",
        )
    await update.message.reply_text("Trip cancelled. Group has been notified.")


travel_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("travel", travel_start)],
    states={
        DESTINATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, travel_destination)],
        DEPART_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, travel_depart)],
        RETURN_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, travel_return)],
        NOTES: [
            CommandHandler("skip", travel_skip_notes),
            MessageHandler(filters.TEXT & ~filters.COMMAND, travel_notes),
        ],
        COMPANIONS: [CallbackQueryHandler(travel_companions, pattern=r"^travelcomp_")],
    },
    fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    per_message=False,
)
