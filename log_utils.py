import html
import logging
import platform
from datetime import datetime
from typing import Optional, Union

import aiohttp
from pyrogram import Client

from config import LOG_CHAT_ID, BOT_USERNAME, BOT_TOKEN

logger = logging.getLogger(__name__)

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
                lowered = desc.lower()
                if any(x in lowered for x in ["chat not found", "bot was kicked", "not enough rights", "forbidden"]):
                    _LOG_DISABLED = True
                return False, desc
    except Exception as exc:
        return False, str(exc)


async def send_log(client: Client, text: str, *, disable_web_page_preview: bool = True) -> bool:
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
    """Startup report — plain text, small caps style, no image."""
    chat_id = _chat_id()
    if not chat_id:
        return

    try:
        bot = await client.get_me()
        bot_name     = bot.first_name or BOT_USERNAME
        bot_username = f"@{bot.username}" if bot.username else BOT_USERNAME
        pyrogram_version = __import__("pyrogram").__version__

        # ── Small caps startup message ───────────────────────
        caption = (
            "╔════════════════════╗\n"
            "ɴᴏᴍᴀᴅᴇ ʜᴇʟᴘ ʙᴏᴛ\n"
            "╚════════════════════╝\n\n"
            f"⌬ ꜱᴛᴀᴛᴜꜱ      : ᴏɴʟɪɴᴇ\n"
            f"⌬ ʙᴏᴛ         : {bot_name}\n"
            f"⌬ ᴜꜱᴇʀɴᴀᴍᴇ    : {bot_username}\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"⌬ ᴘʏᴛʜᴏɴ      : v{platform.python_version()}\n"
            f"⌬ ᴘʏʀᴏɢʀᴀᴍ    : v{pyrogram_version}\n"
            f"⌬ ᴏꜱ          : {platform.system()} {platform.release()}\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "⌬ ᴜᴘᴛɪᴍᴇ      : ᴀᴄᴛɪᴠᴇ\n"
            "⌬ ᴍᴏᴅᴇ        : ɴᴏᴍᴀᴅᴇ ᴘᴏᴡᴇʀ\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "ɴᴏᴍᴀᴅᴇ ꜱʏꜱᴛᴇᴍ\n"
            "ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴀᴄᴛɪᴠᴀᴛᴇᴅ\n\n"
            "╚════════════════════╝"
        )

        # Send as plain text — no image
        ok, info = await _bot_api(
            "sendMessage",
            {
                "chat_id": str(chat_id),
                "text": caption,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            },
        )
        if not ok:
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
