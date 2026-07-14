from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import FAMILY
from database import delete_plan, get_user_upcoming_plans, save_plan
from utils import format_date, get_current_weekend_start, normalize_username, now_sgt, parse_date, remove_keyboard_row

CHOOSE_DAY, ENTER_DAY, PLAN_TEXT = range(3)
CANCEL_DAY = 0


def _weekend_keyboard():
    from utils import get_weekend_dates, format_date
    sat, sun = get_weekend_dates()
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"Saturday ({sat.day} {sat.strftime('%b')})", callback_data=f"planday_{sat}"),
            InlineKeyboardButton(f"Sunday ({sun.day} {sun.strftime('%b')})",   callback_data=f"planday_{sun}"),
        ],
        [InlineKeyboardButton("A different day →", callback_data="planday_other")],
    ])


# ── /plan ─────────────────────────────────────────────────────────────────────

async def plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if normalize_username(update.effective_user.username) not in FAMILY:
        await update.message.reply_text("You're not in the Tay family group!")
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        "Which day are you planning for?",
        reply_markup=_weekend_keyboard(),
    )
    return CHOOSE_DAY


async def chose_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "planday_other":
        await query.edit_message_text(
            "Which day? e.g. *Monday*, *5 Jun*, *today*, *tomorrow*",
            parse_mode="Markdown",
        )
        return ENTER_DAY

    date_str = query.data.replace("planday_", "")
    context.user_data["plan_date"] = date_str
    context.user_data["plan_date_label"] = format_date(date_str)
    await query.edit_message_text(
        f"What are your plans for *{context.user_data['plan_date_label']}*?",
        parse_mode="Markdown",
    )
    return PLAN_TEXT


async def entered_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = parse_date(update.message.text)
    if not d:
        await update.message.reply_text(
            "Couldn't read that. Try *Monday*, *5 Jun*, *today*, or *28/6*.",
            parse_mode="Markdown",
        )
        return ENTER_DAY

    context.user_data["plan_date"] = str(d)
    context.user_data["plan_date_label"] = format_date(str(d))
    await update.message.reply_text(
        f"What are your plans for *{context.user_data['plan_date_label']}*?",
        parse_mode="Markdown",
    )
    return PLAN_TEXT


async def got_plan_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = normalize_username(update.effective_user.username)
    date_str = context.user_data["plan_date"]
    label    = context.user_data["plan_date_label"]

    await save_plan(username, date_str, update.message.text.strip())

    name = FAMILY.get(username, f"@{username}")
    await update.message.reply_text(f"Saved! {name}'s plans for *{label}* updated. 👍", parse_mode="Markdown")
    return ConversationHandler.END


async def plan_cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("No worries, cancelled.")
    return ConversationHandler.END


async def planedit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    date_str = query.data.split("_", 1)[1]
    await query.answer()

    context.user_data.clear()
    context.user_data["plan_date"] = date_str
    context.user_data["plan_date_label"] = format_date(date_str)
    await query.message.reply_text(
        f"What are your new plans for *{context.user_data['plan_date_label']}*?",
        parse_mode="Markdown",
    )
    return PLAN_TEXT


plan_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("plan", plan_start),
        CallbackQueryHandler(planedit_start, pattern=r"^planedit_"),
    ],
    states={
        CHOOSE_DAY: [CallbackQueryHandler(chose_day,    pattern="^planday_")],
        ENTER_DAY:  [MessageHandler(filters.TEXT & ~filters.COMMAND, entered_day)],
        PLAN_TEXT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_plan_text)],
    },
    fallbacks=[CommandHandler("cancel", plan_cancel_wizard)],
    allow_reentry=True,
    per_message=False,
)


async def plancancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    username = normalize_username(query.from_user.username)
    date_str = query.data.split("_", 1)[1]

    deleted = await delete_plan(username, date_str)
    if not deleted:
        await query.answer("No plan found for that date.", show_alert=True)
        return

    await query.answer("Plan cancelled.")
    try:
        new_kb = remove_keyboard_row(query.message.reply_markup.inline_keyboard, date_str)
        await query.edit_message_reply_markup(InlineKeyboardMarkup(new_kb))
    except Exception:
        pass


# ── /cancelplan ───────────────────────────────────────────────────────────────

async def cancelplan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if normalize_username(update.effective_user.username) not in FAMILY:
        await update.message.reply_text("You're not in the Tay family group!")
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        "Which day's plans do you want to cancel? e.g. *Saturday*, *5 Jun*",
        parse_mode="Markdown",
    )
    return CANCEL_DAY


async def got_cancel_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = parse_date(update.message.text)
    if not d:
        await update.message.reply_text(
            "Couldn't read that. Try *Saturday*, *5 Jun*, or *28/6*.",
            parse_mode="Markdown",
        )
        return CANCEL_DAY

    username = normalize_username(update.effective_user.username)
    deleted  = await delete_plan(username, str(d))
    label    = format_date(str(d))

    if deleted:
        await update.message.reply_text(f"Done — your plans for *{label}* have been removed.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"No plans found for *{label}*.", parse_mode="Markdown")
    return ConversationHandler.END


cancelplan_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("cancelplan", cancelplan_start)],
    states={
        CANCEL_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_cancel_day)],
    },
    fallbacks=[CommandHandler("cancel", plan_cancel_wizard)],
    allow_reentry=True,
)


# ── /myplans ──────────────────────────────────────────────────────────────────

async def myplans_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = normalize_username(update.effective_user.username)
    if username not in FAMILY:
        await update.message.reply_text("You're not in the Tay family group!")
        return

    today = str(now_sgt().date())
    plans = await get_user_upcoming_plans(username, today)

    name = FAMILY.get(username, f"@{username}")
    if not plans:
        await update.message.reply_text(
            f"No upcoming plans saved for you, {name}. Use /plan to add some!", parse_mode="Markdown"
        )
        return

    lines         = [f"*{name}'s upcoming plans:*\n"]
    keyboard_rows = []
    for p in plans:
        lines.append(f"• *{format_date(p['date'])}*: {p['plan_text']}")
        keyboard_rows.append([
            InlineKeyboardButton("✏️ Edit",   callback_data=f"planedit_{p['date']}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"plancancel_{p['date']}"),
        ])

    await update.message.reply_text(
        "\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard_rows)
    )
