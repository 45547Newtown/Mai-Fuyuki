# ============================================================
# Start / Help handlers
# ============================================================

import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import BOT_USERNAME, OWNER_ID
import db

logger = logging.getLogger(__name__)

START_TEXT = """Hey there! My name is Mai Fuyuki - I'm here to help you manage your groups! Use /help to find out how to use me to my full potential.

Join my news channel to get information on all the latest updates.

Check /privacy to view the privacy policy, and interact with your data."""


def add_me_keyboard():
    username = (BOT_USERNAME or "Mai_Fuyuki_bot").lstrip("@")
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⚒ Add me to your Group ⚒", url=f"https://t.me/{username}?startgroup=true")]]
    )


def register_handlers(app: Client):
    # ==========================================================
    # Start Command - TEXT ONLY + ONE BUTTON ONLY
    # ==========================================================
    @app.on_message(filters.private & filters.command("start"), group=-100)
    async def start_command(client, message):
        user = message.from_user

        # Reply first. No image, no news/help buttons.
        await message.reply_text(
            START_TEXT,
            reply_markup=add_me_keyboard(),
            disable_web_page_preview=True,
        )

        # DB save should never block /start response.
        try:
            if user:
                await db.add_user(user.id, user.first_name)
        except Exception as exc:
            logger.warning("Failed to save /start user %s: %s", user.id if user else None, exc)

    # ==========================================================
    # Help Command - simple text only
    # ==========================================================
    @app.on_message(filters.private & filters.command("help"))
    async def help_command(client, message):
        await message.reply_text(
            "Use me in groups to manage welcome, locks and moderation commands.",
            reply_markup=add_me_keyboard(),
            disable_web_page_preview=True,
        )

    # ==========================================================
    # Privacy Command
    # ==========================================================
    @app.on_message(filters.private & filters.command("privacy"))
    async def privacy_command(client, message):
        await message.reply_text(
            "Privacy: I only use your Telegram user/chat data for bot features like group management, logs and settings.",
            disable_web_page_preview=True,
        )

    # ==========================================================
    # Broadcast Command
    # ==========================================================
    @app.on_message(filters.private & filters.command("broadcast"))
    async def broadcast_message(client, message):
        if message.from_user.id != OWNER_ID:
            await message.reply_text("❌ Only the bot owner can use this command.")
            return

        if not message.reply_to_message:
            await message.reply_text("⚠️ Please reply to a message to broadcast it.")
            return

        text_to_send = message.reply_to_message.text or message.reply_to_message.caption
        if not text_to_send:
            await message.reply_text("⚠️ The replied message has no text to send.")
            return

        users = await db.get_all_users()
        sent = 0
        failed = 0

        for user_id in users:
            try:
                await client.send_message(user_id, text_to_send)
                sent += 1
            except Exception:
                failed += 1

        await message.reply_text(f"✅ Broadcast complete.\nSent: {sent}\nFailed: {failed}")
