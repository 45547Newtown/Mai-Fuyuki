# ============================================================
# Group Manager Bot — Auto Delete Scheduler
# plugin/autodelete_system/scheduler.py
#
# Intercepts every incoming message in groups where auto-delete
# is active and schedules asyncio.sleep + delete_messages.
# ============================================================

import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import MessageDeleteForbidden, MessageIdInvalid, FloodWait

from db_autodelete import get_autodelete

logger = logging.getLogger(__name__)


def _is_media(message: Message) -> bool:
    """Return True if the message carries a media attachment."""
    return bool(
        message.photo
        or message.video
        or message.document
        or message.audio
        or message.voice
        or message.video_note
        or message.sticker
        or message.animation
    )


async def _delete_after(client: Client, chat_id: int, message_id: int, delay: int):
    """Wait `delay` seconds then attempt to delete the message."""
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id, message_id)
        logger.debug("🗑️ Deleted msg %s in chat %s", message_id, chat_id)
    except (MessageDeleteForbidden, MessageIdInvalid):
        # Already deleted or bot lost permission — ignore quietly
        pass
    except FloodWait as e:
        # Telegram rate-limit: wait and retry once
        await asyncio.sleep(e.value + 2)
        try:
            await client.delete_messages(chat_id, message_id)
        except Exception:
            pass
    except Exception as exc:
        logger.warning("AutoDelete error (chat=%s, msg=%s): %s", chat_id, message_id, exc)


async def message_watcher(client: Client, message: Message):
    """
    Handler group=10.
    Checks auto-delete settings for this chat and, if active,
    schedules deletion for matching message types.
    """
    chat_id = message.chat.id
    cfg = await get_autodelete(chat_id)

    if not cfg["enabled"] or cfg["seconds"] <= 0:
        return

    mode    = cfg["mode"]     # 'messages' | 'media' | 'all'
    seconds = cfg["seconds"]
    is_med  = _is_media(message)

    should_delete = (
        mode == "all"
        or (mode == "media"    and is_med)
        or (mode == "messages" and not is_med)
    )

    if should_delete:
        asyncio.create_task(
            _delete_after(client, chat_id, message.id, seconds)
        )


def register_autodelete_scheduler(app: Client):
    app.on_message(
        filters.group & ~filters.service,
        group=10,
    )(message_watcher)
    logger.info("✅ AutoDelete scheduler registered.")
