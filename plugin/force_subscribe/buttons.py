# ============================================================
# Force Subscribe / Welcome Buttons Plugin
# plugin/force_subscribe/buttons.py
#
# Commands:
#   /setwelcomebutton  - Button add karo (Admin only)
#   /clearwelcomebutton - Sab buttons hata do (Admin only)
#   /welcomebuttons    - Current buttons dekho (Admin only)
#
# Usage:
#   /setwelcomebutton YouTube Channel | https://youtube.com/@yourchannel
#   /setwelcomebutton YouTube Channel | https://youtube.com
#   Tutorial Channel | https://t.me/yourchannel
# ============================================================

import logging
import db

from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from pyrogram.enums import ChatMemberStatus

logger = logging.getLogger(__name__)


# ----------------------------------------------------------
# Helper: Admin check
# ----------------------------------------------------------

async def _is_admin(client, chat_id: int, user_id: int) -> bool:
    member = await client.get_chat_member(chat_id, user_id)
    return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]


# ----------------------------------------------------------
# Helper: Parse button lines
#   Format: "Button Text | https://link.com"
#   Multiple buttons = each on new line
# ----------------------------------------------------------

def _parse_buttons(raw_text: str):
    buttons = []
    errors = []

    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if "|" not in line:
            errors.append(f"❌ `{line}` — `|` missing hai")
            continue
        parts = line.split("|", 1)
        text = parts[0].strip()
        url = parts[1].strip()
        if not url.startswith("http"):
            errors.append(f"❌ Invalid URL: `{url}`")
            continue
        if not text:
            errors.append(f"❌ Button ka naam khali hai")
            continue
        buttons.append({"text": text, "url": url})

    return buttons, errors


# ----------------------------------------------------------
# Build InlineKeyboardMarkup from saved buttons
# ----------------------------------------------------------

def build_keyboard(saved_buttons: list) -> InlineKeyboardMarkup | None:
    if not saved_buttons:
        return None
    keyboard = [
        [InlineKeyboardButton(btn["text"], url=btn["url"])]
        for btn in saved_buttons
    ]
    return InlineKeyboardMarkup(keyboard)


# ----------------------------------------------------------
# Register all force_subscribe handlers
# ----------------------------------------------------------

def register_force_subscribe(app):

    # ======================================================
    # /setwelcomebutton — Buttons set karo
    # ======================================================

    @app.on_message(filters.group & filters.command("setwelcomebutton"))
    async def set_welcome_button(client, message: Message):
        if not await _is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Sirf admin yeh command use kar sakta hai.")

        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply_text(
                "📌 **Usage:**\n"
                "`/setwelcomebutton Button Name | https://link.com`\n\n"
                "**Multiple buttons ke liye har ek naye line pe likho:**\n"
                "```\n"
                "/setwelcomebutton YouTube Channel | https://youtube.com/@channel\n"
                "Tutorial Channel | https://t.me/channel\n"
                "```"
            )

        buttons, errors = _parse_buttons(parts[1])

        if not buttons:
            msg = "⚠️ Koi valid button nahi mila.\n\n"
            msg += "**Format:** `Button Name | https://link.com`"
            if errors:
                msg += "\n\n" + "\n".join(errors)
            return await message.reply_text(msg)

        await db.set_welcome_buttons(message.chat.id, buttons)

        btn_list = "\n".join([f"• {b['text']} → {b['url']}" for b in buttons])
        reply = f"✅ **{len(buttons)} button(s) save ho gaye!**\n\n{btn_list}"
        if errors:
            reply += "\n\n⚠️ **Kuch lines skip hui:**\n" + "\n".join(errors)

        await message.reply_text(reply)


    # ======================================================
    # /clearwelcomebutton — Sab buttons delete karo
    # ======================================================

    @app.on_message(filters.group & filters.command("clearwelcomebutton"))
    async def clear_welcome_button(client, message: Message):
        if not await _is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Sirf admin yeh command use kar sakta hai.")

        await db.clear_welcome_buttons(message.chat.id)
        await message.reply_text("🗑️ Welcome buttons hata diye gaye!")


    # ======================================================
    # /welcomebuttons — Current buttons dekho
    # ======================================================

    @app.on_message(filters.group & filters.command("welcomebuttons"))
    async def show_welcome_buttons(client, message: Message):
        if not await _is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Sirf admin yeh command use kar sakta hai.")

        saved = await db.get_welcome_buttons(message.chat.id)
        if not saved:
            return await message.reply_text("ℹ️ Abhi koi welcome button set nahi hai.")

        btn_list = "\n".join(
            [f"{i+1}. {b['text']} → {b['url']}" for i, b in enumerate(saved)]
        )
        await message.reply_text(
            f"📋 **Current Welcome Buttons ({len(saved)}):**\n\n{btn_list}",
            reply_markup=build_keyboard(saved)
        )
