# ============================================================
# Group Manager Bot — Auto Delete System
# plugin/autodelete_system/commands.py
#
# Supports:
#   /autodelete_on            – Enable with last saved settings
#   /autodelete_off           – Disable auto delete
#   /autodelete_1day          – Delete messages after 1 day
#   /autodelete_1week         – Delete messages after 1 week
#   /autodelete_1month        – Delete messages after 1 month
#   /autodelete_custom        – Prompt for custom time (10m, 12h, 7d)
#   /autodelete_media_1day    – Delete media after 1 day
#   /autodelete_media_1week   – Delete media after 1 week
#   /autodelete_media_1month  – Delete media after 1 month
#   /autodelete_all_1day      – Delete msgs + media after 1 day
#   /autodelete_all_1week     – Delete msgs + media after 1 week
#   /autodelete_all_1month    – Delete msgs + media after 1 month
#
# Admin-only. Shows inline quick-select buttons.
# ============================================================

import re
import logging
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from pyrogram.enums import ChatMemberStatus

from db_autodelete import (
    set_autodelete,
    get_autodelete,
    disable_autodelete,
)

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────
SECONDS_1DAY   = 86_400
SECONDS_1WEEK  = 604_800
SECONDS_1MONTH = 2_592_000   # 30 days

# Users waiting for a custom time input  {chat_id: user_id}
_awaiting_custom: dict[int, int] = {}


# ── Helpers ────────────────────────────────────────────────

def _format_duration(seconds: int) -> str:
    """Return a human-readable duration string."""
    if seconds >= SECONDS_1MONTH:
        return f"{seconds // SECONDS_1MONTH} month(s)"
    if seconds >= SECONDS_1WEEK:
        return f"{seconds // SECONDS_1WEEK} week(s)"
    if seconds >= SECONDS_1DAY:
        return f"{seconds // SECONDS_1DAY} day(s)"
    if seconds >= 3600:
        return f"{seconds // 3600} hour(s)"
    return f"{seconds // 60} minute(s)"


def _parse_custom_time(text: str) -> int | None:
    """
    Parse user input like '10m', '12h', '7d', '2w', '1mo'.
    Returns seconds, or None if unrecognised.
    """
    text = text.strip().lower()
    match = re.fullmatch(r"(\d+)(m|h|d|w|mo)", text)
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    multipliers = {"m": 60, "h": 3600, "d": 86400, "w": 604800, "mo": 2592000}
    return value * multipliers[unit]


async def _is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    """Return True if user is an admin or creator in the chat."""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception:
        return False


def _main_keyboard() -> InlineKeyboardMarkup:
    """Quick-select inline keyboard shown with every autodelete command."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏱ 1 Day",    callback_data="ad:msg:1d"),
            InlineKeyboardButton("📅 1 Week",   callback_data="ad:msg:1w"),
            InlineKeyboardButton("🗓 1 Month",  callback_data="ad:msg:1mo"),
        ],
        [
            InlineKeyboardButton("🖼 Media – 1 Day",   callback_data="ad:media:1d"),
            InlineKeyboardButton("🖼 Media – 1 Week",  callback_data="ad:media:1w"),
        ],
        [
            InlineKeyboardButton("📦 All – 1 Day",    callback_data="ad:all:1d"),
            InlineKeyboardButton("📦 All – 1 Week",   callback_data="ad:all:1w"),
            InlineKeyboardButton("📦 All – 1 Month",  callback_data="ad:all:1mo"),
        ],
        [
            InlineKeyboardButton("✏️ Custom Time",   callback_data="ad:custom"),
            InlineKeyboardButton("🔴 Turn Off",       callback_data="ad:off"),
        ],
    ])


def _mode_label(mode: str) -> str:
    labels = {"messages": "Messages", "media": "Media Only", "all": "Messages & Media"}
    return labels.get(mode, mode.title())


async def _apply_and_reply(
    client: Client,
    message: Message,
    mode: str,
    seconds: int,
):
    """Save config and send formatted confirmation."""
    chat_id = message.chat.id
    await set_autodelete(chat_id, mode, seconds, enabled=True)

    duration = _format_duration(seconds)
    mode_text = _mode_label(mode)

    text = (
        f"✅ **Auto Delete Enabled**\n\n"
        f"🗑️ **Scope :** {mode_text}\n"
        f"⏳ **Delete after :** {duration}\n\n"
        f"New {mode_text.lower()} will be automatically deleted "
        f"after **{duration}**.\n\n"
        f"_Use /autodelete\\_off to disable._"
    )
    await message.reply_text(text, reply_markup=_main_keyboard())


# ── Admin guard decorator ──────────────────────────────────

def admin_only(func):
    """Decorator: silently ignore non-admins."""
    async def wrapper(client: Client, message: Message):
        if message.chat.type.value == "private":
            await message.reply_text("⚠️ This command only works in groups/channels.")
            return
        if not await _is_admin(client, message.chat.id, message.from_user.id):
            await message.reply_text("🚫 Only group admins can use this command.")
            return
        await func(client, message)
    return wrapper


# ── Command handlers ───────────────────────────────────────

@admin_only
async def cmd_autodelete_on(client: Client, message: Message):
    cfg = await get_autodelete(message.chat.id)
    if cfg["seconds"] == 0:
        await set_autodelete(message.chat.id, "all", SECONDS_1DAY, enabled=True)
        cfg = {"mode": "all", "seconds": SECONDS_1DAY}

    await set_autodelete(message.chat.id, cfg["mode"], cfg["seconds"], enabled=True)
    duration = _format_duration(cfg["seconds"])
    mode_text = _mode_label(cfg["mode"])

    text = (
        f"✅ **Auto Delete Re-enabled**\n\n"
        f"🗑️ **Scope :** {mode_text}\n"
        f"⏳ **Delete after :** {duration}\n\n"
        f"_Use /autodelete\\_off to disable._"
    )
    await message.reply_text(text, reply_markup=_main_keyboard())


@admin_only
async def cmd_autodelete_off(client: Client, message: Message):
    await disable_autodelete(message.chat.id)
    await message.reply_text(
        "🔴 **Auto Delete Disabled**\n\n"
        "Messages will no longer be automatically deleted.\n\n"
        "_Use /autodelete\\_on to re-enable with previous settings._"
    )


@admin_only
async def cmd_autodelete_1day(client, message):
    await _apply_and_reply(client, message, "messages", SECONDS_1DAY)

@admin_only
async def cmd_autodelete_1week(client, message):
    await _apply_and_reply(client, message, "messages", SECONDS_1WEEK)

@admin_only
async def cmd_autodelete_1month(client, message):
    await _apply_and_reply(client, message, "messages", SECONDS_1MONTH)


@admin_only
async def cmd_autodelete_media_1day(client, message):
    await _apply_and_reply(client, message, "media", SECONDS_1DAY)

@admin_only
async def cmd_autodelete_media_1week(client, message):
    await _apply_and_reply(client, message, "media", SECONDS_1WEEK)

@admin_only
async def cmd_autodelete_media_1month(client, message):
    await _apply_and_reply(client, message, "media", SECONDS_1MONTH)


@admin_only
async def cmd_autodelete_all_1day(client, message):
    await _apply_and_reply(client, message, "all", SECONDS_1DAY)

@admin_only
async def cmd_autodelete_all_1week(client, message):
    await _apply_and_reply(client, message, "all", SECONDS_1WEEK)

@admin_only
async def cmd_autodelete_all_1month(client, message):
    await _apply_and_reply(client, message, "all", SECONDS_1MONTH)


@admin_only
async def cmd_autodelete_custom(client: Client, message: Message):
    """Start custom-time flow: ask admin to type duration."""
    _awaiting_custom[message.chat.id] = message.from_user.id
    await message.reply_text(
        "✏️ **Custom Auto Delete Time**\n\n"
        "Send the duration in one of these formats:\n\n"
        "• `10m`  → 10 minutes\n"
        "• `12h`  → 12 hours\n"
        "• `7d`   → 7 days\n"
        "• `2w`   → 2 weeks\n"
        "• `1mo`  → 1 month\n\n"
        "_Reply with your custom time now:_"
    )


async def handle_custom_time_input(client: Client, message: Message):
    """
    Catches plain text reply when the chat is in custom-time-input mode.
    Registered with a lower group number so it runs after command handlers.
    """
    chat_id = message.chat.id
    if chat_id not in _awaiting_custom:
        return
    if message.from_user.id != _awaiting_custom[chat_id]:
        return

    del _awaiting_custom[chat_id]
    seconds = _parse_custom_time(message.text or "")
    if seconds is None or seconds < 60:
        await message.reply_text(
            "❌ **Invalid format.**\n\n"
            "Please use: `10m`, `12h`, `7d`, `2w`, `1mo`\n"
            "Minimum is 1 minute (`1m`).\n\n"
            "_Run /autodelete\\_custom to try again._"
        )
        return

    await _apply_and_reply(client, message, "all", seconds)


# ── Inline button callbacks ────────────────────────────────

CALLBACK_MAP = {
    "ad:msg:1d":    ("messages", SECONDS_1DAY),
    "ad:msg:1w":    ("messages", SECONDS_1WEEK),
    "ad:msg:1mo":   ("messages", SECONDS_1MONTH),
    "ad:media:1d":  ("media",    SECONDS_1DAY),
    "ad:media:1w":  ("media",    SECONDS_1WEEK),
    "ad:media:1mo": ("media",    SECONDS_1MONTH),
    "ad:all:1d":    ("all",      SECONDS_1DAY),
    "ad:all:1w":    ("all",      SECONDS_1WEEK),
    "ad:all:1mo":   ("all",      SECONDS_1MONTH),
}


async def callback_autodelete(client: Client, query: CallbackQuery):
    chat_id = query.message.chat.id
    user_id = query.from_user.id

    # Admin check for callback too
    if not await _is_admin(client, chat_id, user_id):
        await query.answer("🚫 Only admins can change this.", show_alert=True)
        return

    data = query.data

    if data == "ad:off":
        await disable_autodelete(chat_id)
        await query.answer("🔴 Auto Delete disabled.", show_alert=False)
        await query.message.edit_text(
            "🔴 **Auto Delete Disabled**\n\n"
            "Messages will no longer be automatically deleted.\n\n"
            "_Use /autodelete\\_on to re-enable._"
        )
        return

    if data == "ad:custom":
        _awaiting_custom[chat_id] = user_id
        await query.answer("✏️ Send your custom time now.", show_alert=False)
        await query.message.reply_text(
            "✏️ **Custom Auto Delete Time**\n\n"
            "Send the duration:\n"
            "• `10m` `12h` `7d` `2w` `1mo`"
        )
        return

    if data in CALLBACK_MAP:
        mode, seconds = CALLBACK_MAP[data]
        await set_autodelete(chat_id, mode, seconds, enabled=True)
        duration = _format_duration(seconds)
        mode_text = _mode_label(mode)

        await query.answer(f"✅ {mode_text} — {duration}", show_alert=False)
        await query.message.edit_text(
            f"✅ **Auto Delete Enabled**\n\n"
            f"🗑️ **Scope :** {mode_text}\n"
            f"⏳ **Delete after :** {duration}\n\n"
            f"New {mode_text.lower()} will be automatically deleted "
            f"after **{duration}**.\n\n"
            f"_Use /autodelete\\_off to disable._",
            reply_markup=_main_keyboard(),
        )


# ── Registration ───────────────────────────────────────────

def register_autodelete_system(app: Client):
    app.on_message(filters.command("autodelete_on"))(cmd_autodelete_on)
    app.on_message(filters.command("autodelete_off"))(cmd_autodelete_off)

    app.on_message(filters.command("autodelete_1day"))(cmd_autodelete_1day)
    app.on_message(filters.command("autodelete_1week"))(cmd_autodelete_1week)
    app.on_message(filters.command("autodelete_1month"))(cmd_autodelete_1month)

    app.on_message(filters.command("autodelete_media_1day"))(cmd_autodelete_media_1day)
    app.on_message(filters.command("autodelete_media_1week"))(cmd_autodelete_media_1week)
    app.on_message(filters.command("autodelete_media_1month"))(cmd_autodelete_media_1month)

    app.on_message(filters.command("autodelete_all_1day"))(cmd_autodelete_all_1day)
    app.on_message(filters.command("autodelete_all_1week"))(cmd_autodelete_all_1week)
    app.on_message(filters.command("autodelete_all_1month"))(cmd_autodelete_all_1month)

    app.on_message(filters.command("autodelete_custom"))(cmd_autodelete_custom)

    # Custom time text input (group=5 runs after command handlers)
    app.on_message(
        filters.text & filters.group & ~filters.command(""),
        group=5,
    )(handle_custom_time_input)

    # Inline button callbacks
    app.on_callback_query(filters.regex(r"^ad:"))(callback_autodelete)

    logger.info("✅ AutoDelete system registered.")
