# ============================================================
# plugin/force_sub/force_join.py
#
# Advanced Force Subscribe System with Welcome Security Lock
#
# Features:
#   • Auto-mute new members until they join the required channel
#   • Stylish welcome message with inline buttons (Join / Verify)
#   • Callback verification — unmute on confirmed subscription
#   • Auto-delete messages from unverified users
#   • Admin-only /forcesub_on and /forcesub_off commands
#   • Group-specific enable/disable stored in MongoDB
#   • Admins & owner always bypass restrictions
#   • Handles FloodWait, ChatAdminRequired, UserNotParticipant
# ============================================================

import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    FloodWait,
    UserNotParticipant,
    PeerIdInvalid,
    UserBannedInChannel,
)
from pyrogram.types import (
    CallbackQuery,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import db
from config import OWNER_ID, SUDO_USERS
from plugin.group_guard.group_guard import group_is_approved

logger = logging.getLogger(__name__)

# ── How long (seconds) the "✅ verified" message stays before auto-delete ──
VERIFY_MSG_TTL = 8

# ── Fully locked: no text, media, stickers, GIFs, links, polls, etc. ──────
LOCKED_PERMS = ChatPermissions(
    can_send_messages=False,
    can_send_media_messages=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_send_polls=False,
    can_invite_users=False,
    can_pin_messages=False,
    can_change_info=False,
)

# ── Fully restored permissions ─────────────────────────────────────────────
UNLOCKED_PERMS = ChatPermissions(
    can_send_messages=True,
    can_send_media_messages=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_send_polls=True,
    can_invite_users=True,
)

# ═══════════════════════════════════════════════════════════════
# DATABASE HELPERS  (stored in db.force_sub collection)
# ═══════════════════════════════════════════════════════════════

async def fs_is_enabled(chat_id: int) -> bool:
    doc = await db.db.force_sub.find_one({"chat_id": chat_id})
    return bool(doc.get("enabled", False)) if doc else False


async def fs_set_enabled(chat_id: int, status: bool) -> None:
    await db.db.force_sub.update_one(
        {"chat_id": chat_id},
        {"$set": {"enabled": status}},
        upsert=True,
    )


async def fs_mark_verified(chat_id: int, user_id: int) -> None:
    """Remember that a user passed verification in this chat."""
    await db.db.force_sub_verified.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$set": {"verified": True}},
        upsert=True,
    )


async def fs_is_verified(chat_id: int, user_id: int) -> bool:
    doc = await db.db.force_sub_verified.find_one(
        {"chat_id": chat_id, "user_id": user_id}
    )
    return bool(doc.get("verified", False)) if doc else False


# ═══════════════════════════════════════════════════════════════
# UTILITY HELPERS
# ═══════════════════════════════════════════════════════════════

def _is_privileged(user_id: int) -> bool:
    """Owners and sudo users always bypass force-sub."""
    return user_id == OWNER_ID or user_id in SUDO_USERS


async def _is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    """True if the user is an admin or owner of the group."""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception:
        return False


async def _get_force_sub_channel():
    """
    Returns (channel_id_or_username, join_url) from env/config.
    Reads lazily so config is always fresh.
    """
    import os
    channel = os.getenv("FORCE_SUB_CHANNEL", "").strip()
    url = os.getenv("FORCE_SUB_URL", "").strip()

    if not channel:
        return None, None

    # Accept both @username and numeric id
    if channel.lstrip("-").isdigit():
        channel = int(channel)

    if not url:
        # Build a sensible fallback URL
        if isinstance(channel, str) and channel.startswith("@"):
            url = f"https://t.me/{channel.lstrip('@')}"
        else:
            url = "https://t.me/"          # Fallback — owner should set FORCE_SUB_URL

    return channel, url


async def _user_in_channel(client: Client, channel, user_id: int) -> bool:
    """
    Returns True when the user is a member/subscriber of *channel*.
    Raises nothing — always returns a bool.
    """
    if channel is None:
        return True     # No channel configured → treat as verified
    try:
        member = await client.get_chat_member(channel, user_id)
        return member.status not in (
            ChatMemberStatus.BANNED,
            ChatMemberStatus.LEFT,
        )
    except UserNotParticipant:
        logger.info("ForceSub | user %s is NOT in channel %s", user_id, channel)
        return False
    except (PeerIdInvalid, UserBannedInChannel):
        return False
    except FloodWait as e:
        logger.warning("ForceSub | FloodWait %ss while checking channel membership", e.value)
        await asyncio.sleep(e.value)
        return False
    except Exception as e:
        logger.error("ForceSub | Unexpected error checking membership: %s", e)
        return False


async def _mute_user(client: Client, chat_id: int, user_id: int) -> bool:
    """Restrict user to fully locked permissions. Returns True on success."""
    try:
        await client.restrict_chat_member(chat_id, user_id, LOCKED_PERMS)
        logger.info("ForceSub | 🔇 Muted user %s in chat %s", user_id, chat_id)
        return True
    except ChatAdminRequired:
        logger.warning(
            "ForceSub | ChatAdminRequired — bot lacks restrict permissions in %s", chat_id
        )
        return False
    except FloodWait as e:
        logger.warning("ForceSub | FloodWait %ss while muting user %s", e.value, user_id)
        await asyncio.sleep(e.value)
        return False
    except Exception as e:
        logger.error("ForceSub | Failed to mute user %s in %s: %s", user_id, chat_id, e)
        return False


async def _unmute_user(client: Client, chat_id: int, user_id: int) -> bool:
    """Restore default chat permissions. Returns True on success."""
    try:
        await client.restrict_chat_member(chat_id, user_id, UNLOCKED_PERMS)
        logger.info("ForceSub | 🔓 Unmuted user %s in chat %s", user_id, chat_id)
        return True
    except ChatAdminRequired:
        logger.warning(
            "ForceSub | ChatAdminRequired — bot lacks restrict permissions in %s", chat_id
        )
        return False
    except FloodWait as e:
        logger.warning("ForceSub | FloodWait %ss while unmuting user %s", e.value, user_id)
        await asyncio.sleep(e.value)
        return False
    except Exception as e:
        logger.error("ForceSub | Failed to unmute user %s in %s: %s", user_id, chat_id, e)
        return False


def _welcome_buttons(join_url: str, user_id: int, chat_id: int) -> InlineKeyboardMarkup:
    """Build the two-button inline keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ 📢",
                url=join_url,
            ),
        ],
        [
            InlineKeyboardButton(
                "✅ ɪ ᴊᴏɪɴᴇᴅ — ᴠᴇʀɪꜰʏ",
                callback_data=f"fs_verify:{user_id}:{chat_id}",
            ),
        ],
    ])


def _welcome_text(mention: str, group_name: str) -> str:
    return (
        f"ʜᴇʏ {mention} 👋\n\n"
        f"ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ **{group_name}** 🎉\n\n"
        "━━━━━━━━━━━━━━━━\n\n"
        "ᴛᴏ ꜱᴇɴᴅ ᴍᴇꜱꜱᴀɢᴇꜱ ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ,\n"
        "ʏᴏᴜ **ᴍᴜꜱᴛ** ꜰɪʀꜱᴛ ᴊᴏɪɴ ᴏᴜʀ\n"
        "ᴏꜰꜰɪᴄɪᴀʟ ᴄʜᴀɴɴᴇʟ. 📢\n\n"
        "1️⃣  ᴄʟɪᴄᴋ **ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ** ʙᴇʟᴏᴡ\n"
        "2️⃣  ᴊᴏɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ\n"
        "3️⃣  ᴄᴏᴍᴇ ʙᴀᴄᴋ & ᴘʀᴇꜱꜱ **✅ ɪ ᴊᴏɪɴᴇᴅ**\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "_ʏᴏᴜ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴜɴʟᴏᴄᴋᴇᴅ._"
    )


# ═══════════════════════════════════════════════════════════════
# HANDLER REGISTRATION
# ═══════════════════════════════════════════════════════════════

def register_force_sub_plugin(app: Client) -> None:

    # ── 1. New member joins ────────────────────────────────────
    @app.on_message(filters.new_chat_members & filters.group, group=10)
    async def on_new_member(client: Client, message: Message):
        chat_id = message.chat.id

        # Gate: group must be approved
        if not await group_is_approved(chat_id):
            return

        # Gate: force-sub must be enabled for this group
        if not await fs_is_enabled(chat_id):
            return

        channel, join_url = await _get_force_sub_channel()
        if not channel:
            logger.warning("ForceSub | FORCE_SUB_CHANNEL not configured — skipping.")
            return

        me = await client.get_me()

        for user in message.new_chat_members:
            # Skip the bot itself
            if user.id == me.id:
                continue

            # Skip admins, sudo users, owner
            if _is_privileged(user.id):
                continue
            if await _is_admin(client, chat_id, user.id):
                continue

            # Already verified (rejoined the group)
            if await fs_is_verified(chat_id, user.id):
                continue

            # Check if already in channel
            already_in = await _user_in_channel(client, channel, user.id)
            if already_in:
                await fs_mark_verified(chat_id, user.id)
                continue

            # Mute first
            muted = await _mute_user(client, chat_id, user.id)

            # Send welcome + instructions
            group_name = message.chat.title or "this group"
            mention = user.mention
            text = _welcome_text(mention, group_name)
            buttons = _welcome_buttons(join_url, user.id, chat_id)

            try:
                await message.reply_text(
                    text,
                    reply_markup=buttons,
                    quote=False,
                )
                if muted:
                    logger.info(
                        "ForceSub | New member %s (%s) muted in %s",
                        user.first_name, user.id, chat_id,
                    )
            except FloodWait as e:
                logger.warning("ForceSub | FloodWait %ss on welcome message", e.value)
                await asyncio.sleep(e.value)
            except Exception as e:
                logger.error("ForceSub | Could not send welcome message: %s", e)

    # ── 2. Intercept messages from unverified users ────────────
    @app.on_message(filters.group & ~filters.service, group=5)
    async def on_group_message(client: Client, message: Message):
        chat_id = message.chat.id

        if not message.from_user:
            return

        user_id = message.from_user.id

        if not await group_is_approved(chat_id):
            return
        if not await fs_is_enabled(chat_id):
            return

        # Bypass for privileged users
        if _is_privileged(user_id):
            return
        if await _is_admin(client, chat_id, user_id):
            return

        # Already verified
        if await fs_is_verified(chat_id, user_id):
            return

        # Check live membership
        channel, join_url = await _get_force_sub_channel()
        if not channel:
            return

        in_channel = await _user_in_channel(client, channel, user_id)
        if in_channel:
            # Quietly mark them verified and let the message through
            await fs_mark_verified(chat_id, user_id)
            await _unmute_user(client, chat_id, user_id)
            return

        # Delete the offending message
        try:
            await message.delete()
            logger.info(
                "ForceSub | Deleted message from unverified user %s in chat %s",
                user_id, chat_id,
            )
        except Exception as e:
            logger.warning("ForceSub | Could not delete message: %s", e)

        # Re-mute just in case permissions were restored by someone
        await _mute_user(client, chat_id, user_id)

        # Nudge the user (send a fresh reminder only if no recent one)
        group_name = message.chat.title or "this group"
        mention = message.from_user.mention
        text = _welcome_text(mention, group_name)
        buttons = _welcome_buttons(join_url, user_id, chat_id)

        try:
            reminder = await client.send_message(
                chat_id,
                text,
                reply_markup=buttons,
            )
            # Auto-delete reminder after 30 seconds
            asyncio.get_event_loop().call_later(
                30,
                asyncio.ensure_future,
                _safe_delete(client, chat_id, reminder.id),
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            logger.error("ForceSub | Could not send reminder message: %s", e)

    # ── 3. Verify callback ─────────────────────────────────────
    @app.on_callback_query(filters.regex(r"^fs_verify:(\d+):(-?\d+)$"))
    async def on_verify_callback(client: Client, query: CallbackQuery):
        data_parts = query.data.split(":")
        target_user_id = int(data_parts[1])
        chat_id = int(data_parts[2])

        caller_id = query.from_user.id

        # Only the target user (or an admin) may press Verify
        if caller_id != target_user_id:
            if not (_is_privileged(caller_id) or await _is_admin(client, chat_id, caller_id)):
                await query.answer(
                    "⛔ ᴛʜɪꜱ ʙᴜᴛᴛᴏɴ ɪꜱ ɴᴏᴛ ꜰᴏʀ ʏᴏᴜ.",
                    show_alert=True,
                )
                return

        channel, join_url = await _get_force_sub_channel()
        if not channel:
            await query.answer("⚙️ Force-sub channel is not configured.", show_alert=True)
            return

        # Check membership
        in_channel = await _user_in_channel(client, channel, target_user_id)

        if not in_channel:
            logger.info(
                "ForceSub | Verification FAILED for user %s in chat %s",
                target_user_id, chat_id,
            )
            await query.answer(
                "❌ ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴊᴏɪɴᴇᴅ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ʏᴇᴛ.\n\n"
                "ᴘʟᴇᴀꜱᴇ ᴊᴏɪɴ ꜰɪʀꜱᴛ, ᴛʜᴇɴ ᴄʟɪᴄᴋ ᴠᴇʀɪꜰʏ ᴀɢᴀɪɴ.",
                show_alert=True,
            )
            return

        # ── User is in the channel ─────────────────────────────
        logger.info(
            "ForceSub | ✅ Verification SUCCESS for user %s in chat %s",
            target_user_id, chat_id,
        )

        # Unmute
        unmuted = await _unmute_user(client, chat_id, target_user_id)

        # Persist
        await fs_mark_verified(chat_id, target_user_id)

        # Answer the callback immediately
        await query.answer("✅ ᴠᴇʀɪꜰɪᴇᴅ! ʏᴏᴜ ᴄᴀɴ ɴᴏᴡ ᴄʜᴀᴛ. 🎉", show_alert=False)

        # Edit the welcome message to a success banner
        try:
            user = query.from_user
            success_text = (
                f"✅ **{user.mention}** ʜᴀꜱ ʙᴇᴇɴ ᴠᴇʀɪꜰɪᴇᴅ!\n\n"
                "━━━━━━━━━━━━━━━━\n\n"
                "🎉 ᴡᴇʟᴄᴏᴍᴇ ᴀʙᴏᴀʀᴅ! ʏᴏᴜ ᴄᴀɴ ɴᴏᴡ\n"
                "ꜱᴇɴᴅ ᴍᴇꜱꜱᴀɢᴇꜱ ꜰʀᴇᴇʟʏ. 🚀\n\n"
                "━━━━━━━━━━━━━━━━"
            )
            await query.message.edit_text(success_text)
        except Exception as e:
            logger.warning("ForceSub | Could not edit welcome message: %s", e)

        # Auto-delete the success message after VERIFY_MSG_TTL seconds
        asyncio.get_event_loop().call_later(
            VERIFY_MSG_TTL,
            asyncio.ensure_future,
            _safe_delete(client, query.message.chat.id, query.message.id),
        )

    # ── 4. /forcesub_on ───────────────────────────────────────
    @app.on_message(filters.command("forcesub_on") & filters.group)
    async def cmd_forcesub_on(client: Client, message: Message):
        if not await group_is_approved(message.chat.id):
            return

        if not (
            _is_privileged(message.from_user.id)
            or await _is_admin(client, message.chat.id, message.from_user.id)
        ):
            return await message.reply_text("⛔ ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴜꜱᴇ ᴛʜɪꜱ.")

        channel, join_url = await _get_force_sub_channel()
        if not channel:
            return await message.reply_text(
                "⚠️ **FORCE_SUB_CHANNEL** ɪꜱ ɴᴏᴛ ꜱᴇᴛ ɪɴ ᴇɴᴠɪʀᴏɴᴍᴇɴᴛ ᴠᴀʀɪᴀʙʟᴇꜱ.\n\n"
                "ᴀꜱᴋ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ ᴛᴏ ꜱᴇᴛ:\n"
                "`FORCE_SUB_CHANNEL` = @yourchannel\n"
                "`FORCE_SUB_URL` = https://t.me/yourchannel"
            )

        await fs_set_enabled(message.chat.id, True)
        logger.info("ForceSub | Enabled in chat %s by %s", message.chat.id, message.from_user.id)
        await message.reply_text(
            "✅ **ꜰᴏʀᴄᴇ ꜱᴜʙꜱᴄʀɪʙᴇ** ɪꜱ ɴᴏᴡ **ᴏɴ**\n\n"
            f"📢 ᴄʜᴀɴɴᴇʟ: `{channel}`\n\n"
            "ɴᴇᴡ ᴍᴇᴍʙᴇʀꜱ ᴍᴜꜱᴛ ᴊᴏɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ\n"
            "ʙᴇꜰᴏʀᴇ ᴛʜᴇʏ ᴄᴀɴ ꜱᴇɴᴅ ᴍᴇꜱꜱᴀɢᴇꜱ."
        )

    # ── 5. /forcesub_off ──────────────────────────────────────
    @app.on_message(filters.command("forcesub_off") & filters.group)
    async def cmd_forcesub_off(client: Client, message: Message):
        if not await group_is_approved(message.chat.id):
            return

        if not (
            _is_privileged(message.from_user.id)
            or await _is_admin(client, message.chat.id, message.from_user.id)
        ):
            return await message.reply_text("⛔ ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴜꜱᴇ ᴛʜɪꜱ.")

        await fs_set_enabled(message.chat.id, False)
        logger.info("ForceSub | Disabled in chat %s by %s", message.chat.id, message.from_user.id)
        await message.reply_text(
            "🔕 **ꜰᴏʀᴄᴇ ꜱᴜʙꜱᴄʀɪʙᴇ** ɪꜱ ɴᴏᴡ **ᴏꜰꜰ**\n\n"
            "ᴀʟʟ ᴜꜱᴇʀꜱ ᴄᴀɴ ɴᴏᴡ ꜱᴇɴᴅ\n"
            "ᴍᴇꜱꜱᴀɢᴇꜱ ꜰʀᴇᴇʟʏ."
        )

    # ── 6. /forcesub_status ───────────────────────────────────
    @app.on_message(filters.command("forcesub_status") & filters.group)
    async def cmd_forcesub_status(client: Client, message: Message):
        if not await group_is_approved(message.chat.id):
            return

        if not (
            _is_privileged(message.from_user.id)
            or await _is_admin(client, message.chat.id, message.from_user.id)
        ):
            return await message.reply_text("⛔ ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴜꜱᴇ ᴛʜɪꜱ.")

        enabled = await fs_is_enabled(message.chat.id)
        channel, join_url = await _get_force_sub_channel()

        status_icon = "✅ ᴏɴ" if enabled else "🔕 ᴏꜰꜰ"
        channel_display = f"`{channel}`" if channel else "⚠️ ɴᴏᴛ ꜱᴇᴛ"

        await message.reply_text(
            "📋 **ꜰᴏʀᴄᴇ ꜱᴜʙ ꜱᴛᴀᴛᴜꜱ**\n\n"
            f"━━━━━━━━━━━━━━━━\n\n"
            f"🔘 ꜱᴛᴀᴛᴜꜱ : {status_icon}\n"
            f"📢 ᴄʜᴀɴɴᴇʟ : {channel_display}\n\n"
            f"━━━━━━━━━━━━━━━━"
        )

    logger.info("✅ ForceSub plugin fully loaded.")


# ═══════════════════════════════════════════════════════════════
# INTERNAL COROUTINE HELPERS
# ═══════════════════════════════════════════════════════════════

async def _safe_delete(client: Client, chat_id: int, message_id: int) -> None:
    """Delete a message silently, ignoring all errors."""
    try:
        await client.delete_messages(chat_id, message_id)
    except Exception:
        pass
