import html
import logging
import platform
from datetime import datetime
from typing import Optional, Union

import aiohttp
from pyrogram import Client

from config import LOG_CHAT_ID, START_IMAGE, BOT_USERNAME, BOT_TOKEN

logger = logging.getLogger(__name__)

# Important: Pyrogram/MTProto often throws "Peer id invalid" for private
# channels when only a numeric -100... id is known. Telegram Bot API can send
# to the same -100... id as long as the bot is admin/member, so all log-channel
# messages are sent via Bot API instead of client.send_message().
_LOG_DISABLED = False


def _escape(value) -> str:
    return html.escape(str(value or ""))


def _chat_id() -> Optional[Union[int, str]]:
    return LOG_CHAT_ID or None


async def _bot_api(method: str, payload: dict) -> tuple[bool, str]:
    global _LOG_DISABLED
    if _LOG_DISABLED:
        return False, "log disabled after previous failure"
    if not BOT_TOKEN:
        return False, "BOT_TOKEN missing"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, data=payload) as resp:
                data = await resp.json(content_type=None)
                if data.get("ok"):
                    return True, "ok"
                desc = data.get("description", str(data))
                # Disable only for permanent chat-id/access errors so Render logs stay clean.
                lowered = desc.lower()
                if any(x in lowered for x in ["chat not found", "bot was kicked", "not enough rights", "forbidden"]):
                    _LOG_DISABLED = True
                return False, desc
    except Exception as exc:
        return False, str(exc)


async def send_log(client: Client, text: str, *, disable_web_page_preview: bool = True) -> bool:
    """Send a text log to LOG_CHAT_ID using Telegram Bot API.

    Works for private channels/groups with numeric -100... IDs when the bot is
    added as admin/member. This avoids Pyrogram's MTProto peer-cache issue.
    """
    chat_id = _chat_id()
    if not chat_id:
        return False
    ok, info = await _bot_api(
        "sendMessage",
        {
            "chat_id": str(chat_id),
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true" if disable_web_page_preview else "false",
        },
    )
    if not ok:
        logger.info("Log send skipped: %s", info)
    return ok


async def send_startup_log(client: Client) -> None:
    """CipherElite-style startup report for NomadeHelpBot."""
    chat_id = _chat_id()
    if not chat_id:
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

        # Try photo first; if the image URL/file is invalid, send text instead.
        ok, info = await _bot_api(
            "sendPhoto",
            {
                "chat_id": str(chat_id),
                "photo": START_IMAGE,
                "caption": caption,
                "parse_mode": "HTML",
            },
        )
        if not ok:
            ok2 = await send_log(client, caption)
            if not ok2:
                logger.info("Startup log skipped: %s", info)
    except Exception as exc:
        logger.info("Startup log skipped: %s", exc)


async def log_command(client: Client, message) -> None:
    """Log commands and private messages without breaking normal handlers."""
    if not LOG_CHAT_ID or not message or not message.from_user:
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
        f"<b>Chat:</b> {_escape(chat.title if chat and chat.title else 'Private')} (<code>{chat.id if chat else 'N/A'}</code>)\n"
        f"<b>Message:</b>\n<code>{_escape(text[:3500])}</code>"
    )
    await send_log(client, log_text)
