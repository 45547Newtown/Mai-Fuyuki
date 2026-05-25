# ============================================================
# Group Manager Bot - Start/Help handlers
# ============================================================

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from config import BOT_USERNAME, START_IMAGE
import db
import logging

logger = logging.getLogger(__name__)

START_TEXT = """Hey there! My name is Mai Fuyuki - I'm here to help you manage your groups! Use /help to find out how to use me to my full potential.

Join my news channel to get information on all the latest updates.

Check /privacy to view the privacy policy, and interact with your data."""


def start_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⚒️ Add me to your Group ⚒️",
                    url=f"https://t.me/{BOT_USERNAME}?startgroup=true",
                )
            ]
        ]
    )


def register_handlers(app: Client):

    async def send_start_menu(message, user=None):
        # TEXT ONLY: no image, no news/help buttons. Only Add me to Group button.
        await message.reply_text(
            START_TEXT,
            reply_markup=start_keyboard(),
            disable_web_page_preview=True,
        )

    @app.on_message(filters.private & filters.command("start"), group=-10)
    async def start_command(client, message):
        user = message.from_user

        # Reply first so DB/logging can never block /start.
        await send_start_menu(message, user.first_name if user else "there")

        try:
            if user:
                await db.add_user(user.id, user.first_name)
        except Exception as exc:
            logger.warning("Failed to save /start user %s: %s", user.id if user else None, exc)

    async def send_help_menu(message):
        text = """
╔══════════════════╗
     Help Menu
╚══════════════════╝

Choose a category below to explore commands:
─────────────────────────────
"""
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⌂ Greetings ⌂", callback_data="greetings"),
                InlineKeyboardButton("⌂ Locks ⌂", callback_data="locks"),
            ],
            [InlineKeyboardButton("⌂ Moderation ⌂", callback_data="moderation")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")],
        ])

        try:
            media = InputMediaPhoto(media=START_IMAGE, caption=text)
            await message.edit_media(media=media, reply_markup=buttons)
        except Exception:
            await message.reply_text(text, reply_markup=buttons)

    @app.on_callback_query(filters.regex("help"))
    async def help_callback(client, callback_query):
        await send_help_menu(callback_query.message)
        await callback_query.answer()

    @app.on_callback_query(filters.regex("back_to_start"))
    async def back_to_start_callback(client, callback_query):
        # Back button should show same simple text-only start menu.
        await callback_query.message.reply_text(
            START_TEXT,
            reply_markup=start_keyboard(),
            disable_web_page_preview=True,
        )
        await callback_query.answer()

    @app.on_callback_query(filters.regex("greetings"))
    async def greetings_callback(client, callback_query):
        text = """
╔══════════════════╗
    ⚙ Welcome System
╚══════════════════╝

Commands to Manage Welcome Messages:

- /setwelcome <text> : Set a custom welcome message for your group
- /welcome on        : Enable the welcome messages
- /welcome off       : Disable the welcome messages

Supported Placeholders:
- {username} : Telegram username
- {first_name} : User's first name
- {id} : User ID
- {mention} : Mention user in message

Example:
 /setwelcome Hello {first_name}! Welcome to {title}!
"""
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help")]])
        media = InputMediaPhoto(media=START_IMAGE, caption=text)
        await callback_query.message.edit_media(media=media, reply_markup=buttons)
        await callback_query.answer()

    @app.on_callback_query(filters.regex("locks"))
    async def locks_callback(client, callback_query):
        text = """
╔══════════════════╗
     ⚙ Locks System
╚══════════════════╝

Commands to Manage Locks:

- /lock <type>    : Enable a lock for the group
- /unlock <type>  : Disable a lock for the group
- /locks          : Show currently active locks

Available Lock Types:
- url       : Block links
- sticker   : Block stickers
- media     : Block photos/videos/gifs
- username  : Block messages with @username mentions
- language  : Block non-English messages

Example:
 /lock url       : Blocks any messages containing links
 /unlock sticker : Allows stickers again
"""
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help")]])
        media = InputMediaPhoto(media=START_IMAGE, caption=text)
        await callback_query.message.edit_media(media=media, reply_markup=buttons)
        await callback_query.answer()

    @app.on_callback_query(filters.regex("moderation"))
    async def info_callback(client, callback_query):
        text = """
╔══════════════════╗
      ⚙️ Moderation System
╚══════════════════╝

Manage your group easily with these tools:

¤ /kick <user> — Remove a user
¤ /ban <user> — Ban permanently
¤ /unban <user> — Lift ban
¤ /mute <user> — Disable messages
¤ /unmute <user> — Allow messages again
¤ /warn <user> — Add warning (3 = mute)
¤ /warns <user> — View warnings
¤ /resetwarns <user> — Clear all warnings
¤ /promote <user> — make admin
¤ /demote <user> — remove from admin

💡 Example:
Reply to a user or type
<code>/ban @username</code>
"""
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help")]])
        media = InputMediaPhoto(media=START_IMAGE, caption=text)
        await callback_query.message.edit_media(media=media, reply_markup=buttons)
        await callback_query.answer()
