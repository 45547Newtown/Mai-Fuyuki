from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import BOT_USERNAME
from app import app


@app.on_message(filters.command("start") & filters.private, group=-100)
async def start_command(client, message):

    text = """Hey there! My name is Mai Fuyuki - I'm here to help you manage your groups! Use /help to find out how to use me to my full potential.

Join my news channel to get information on all the latest updates.

Check /privacy to view the privacy policy, and interact with your data."""

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⚒ Add me to your Group ⚒",
                    url=f"https://t.me/{BOT_USERNAME}?startgroup=true"
                )
            ]
        ]
    )

    await message.reply_text(
        text=text,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )
