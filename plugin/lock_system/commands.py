# ============================================================
# Mai Fuyuki - Lock System Plugin
# Commands: /lock, /unlock, /locks
# ============================================================

import re
import logging

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, MessageEntityType

import db

logger = logging.getLogger(__name__)

VALID_LOCKS = ["url", "sticker", "media", "username", "forward"]


async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    member = await client.get_chat_member(chat_id, user_id)
    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)


def _usage_text() -> str:
    return (
        "⚙️ Usage:\n"
        "• /lock all\n"
        "• /unlock all\n"
        "• /lock url | sticker | media | username | forward\n"
        "• /unlock url | sticker | media | username | forward"
    )


async def _set_many_locks(chat_id: int, lock_type: str, status: bool):
    if lock_type == "all":
        for item in VALID_LOCKS:
            await db.set_lock(chat_id, item, status)
        return VALID_LOCKS

    await db.set_lock(chat_id, lock_type, status)
    return [lock_type]


def _has_url(message) -> bool:
    text = message.text or message.caption or ""

    # Telegram URL entities
    for ent in (message.entities or message.caption_entities or []):
        if ent.type in (MessageEntityType.URL, MessageEntityType.TEXT_LINK):
            return True

    # Plain links
    return bool(re.search(r"(https?://|www\.|t\.me/|telegram\.me/)", text, flags=re.I))


def _has_username(message) -> bool:
    text = message.text or message.caption or ""
    return bool(re.search(r"(^|\s)@[A-Za-z0-9_]{5,32}\b", text))


def register_lock_system(app: Client):

    @app.on_message(filters.group & filters.command("lock"), group=-10)
    async def lock_command(client, message):
        if not message.from_user or not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admins can use this command.")

        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply_text(_usage_text())

        lock_type = parts[1].lower().strip()
        if lock_type not in ["all"] + VALID_LOCKS:
            return await message.reply_text(f"⚠️ Available: all, {', '.join(VALID_LOCKS)}")

        locked = await _set_many_locks(message.chat.id, lock_type, True)
        if lock_type == "all":
            return await message.reply_text("🔒 Locked all.")
        await message.reply_text(f"🔒 Locked {locked[0]}.")

    @app.on_message(filters.group & filters.command("unlock"), group=-10)
    async def unlock_command(client, message):
        if not message.from_user or not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admins can use this command.")

        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply_text(_usage_text())

        lock_type = parts[1].lower().strip()
        if lock_type not in ["all"] + VALID_LOCKS:
            return await message.reply_text(f"⚠️ Available: all, {', '.join(VALID_LOCKS)}")

        unlocked = await _set_many_locks(message.chat.id, lock_type, False)
        if lock_type == "all":
            return await message.reply_text("🔓 Unlocked all.")
        await message.reply_text(f"🔓 Unlocked {unlocked[0]}.")

    @app.on_message(filters.group & filters.command("locks"), group=-10)
    async def locks_list(client, message):
        locks = await db.get_locks(message.chat.id) or {}
        text = "🔐 **Locks:**\n\n"
        for item in VALID_LOCKS:
            text += f"• {item}: {'✅' if locks.get(item) else '❌'}\n"
        await message.reply_text(text)

    @app.on_message(filters.group & ~filters.service, group=50)
    async def enforce_locks(client, message):
        if not message.from_user:
            return

        try:
            if await is_admin(client, message.chat.id, message.from_user.id):
                return
        except Exception:
            return

        locks = await db.get_locks(message.chat.id) or {}
        if not locks:
            return

        should_delete = False

        if locks.get("url") and _has_url(message):
            should_delete = True
        elif locks.get("sticker") and message.sticker:
            should_delete = True
        elif locks.get("media") and (message.photo or message.video or message.document or message.animation or message.audio or message.voice or message.video_note):
            should_delete = True
        elif locks.get("username") and _has_username(message):
            should_delete = True
        elif locks.get("forward") and (message.forward_from or message.forward_from_chat or message.forward_sender_name):
            should_delete = True

        if should_delete:
            try:
                await message.delete()
            except Exception as exc:
                logger.warning("Failed to delete locked message: %s", exc)
