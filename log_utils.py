import html
import logging
import platform
from datetime import datetime
from typing import Optional

from pyrogram import Client
from pyrogram.enums import ParseMode

from config import LOG_CHAT_ID, START_IMAGE, SUPPORT_GROUP, UPDATE_CHANNEL, BOT_USERNAME

logger = logging.getLogger(__name__)


def _escape(value) -> str:
    return html.escape(str(value or ""))


async def send_log(client: Client, text: str, *, disable_web_page_preview: bool = True) -> bool:
    """Send a message to LOG_CHAT_ID if configured.

    The bot must already be added to the log group/channel. For private channels,
    add the bot as admin and set LOG_CHAT_ID to the -100... id.
    """
    if not LOG_CHAT_ID:
        return False
    try:
        await client.send_message(
            LOG_CHAT_ID,
            text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=disable_web_page_preview,
        )
        return True
    except Exception as exc:
        logger.warning("Failed to send log message to LOG_CHAT_ID=%s: %s", LOG_CHAT_ID, exc)
        return False


async def send_startup_log(client: Client) -> None:
    """CipherElite-style startup report for NomadeHelpBot."""
    if not LOG_CHAT_ID:
        logger.warning("LOG_CHAT_ID is not set; startup log skipped.")
        return

    try:
        bot = await client.get_me()
        bot_name = _escape(bot.first_name or BOT_USERNAME)
        bot_username = f"@{bot.username}" if bot.username else _escape(BOT_USERNAME)
        started_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        pyrogram_version = __import__("pyrogram").__version__

        caption = (
            "<b>=====================</b>\n"
            "<b>NOMADE HELP BOT</b>\n"
            "<b>=====================</b>\n"
            "<b>Status</b>: ONLINE ✅\n"
            f"<b>Bot</b>: {bot_name} (<code>{bot.id}</code>)\n"
            f"<b>Username</b>: {_escape(bot_username)}\n"
            f"<b>Python</b>: v{platform.python_version()}\n"
            f"<b>Pyrogram</b>: v{pyrogram_version}\n"
            f"<b>OS</b>: {_escape(platform.system())} {_escape(platform.release())}\n"
            f"<b>Started</b>: {started_at}\n"
            "<b>=====================</b>\n"
            "<b>Nomade Power Activated!</b>"
        )

        try:
            await client.send_photo(
                LOG_CHAT_ID,
                photo=START_IMAGE,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await client.send_message(LOG_CHAT_ID, caption, parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.warning("Startup log failed: %s", exc)


async def log_command(client: Client, message) -> None:
    """Log commands and private messages without breaking normal handlers."""
    if not LOG_CHAT_ID or not message or not message.from_user:
        return
    if message.chat and message.chat.id == LOG_CHAT_ID:
        return

    user = message.from_user
    chat = message.chat
    text = message.text or message.caption or "<non-text message>"

    is_command = isinstance(text, str) and text.startswith("/")
    is_private = bool(chat and chat.type and str(chat.type).endswith("PRIVATE"))
    if not is_command and not is_private:
        return

    log_text = (
        "<b>📥 NomadeHelpBot Log</b>\n\n"
        f"<b>User:</b> {_escape(user.first_name)} (<code>{user.id}</code>)\n"
        f"<b>Username:</b> @{_escape(user.username) if user.username else 'None'}\n"
        f"<b>Chat:</b> {_escape(chat.title if chat else 'Private')} (<code>{chat.id if chat else 'N/A'}</code>)\n"
        f"<b>Message:</b>\n<code>{_escape(text[:3500])}</code>"
    )
    await send_log(client, log_text)
