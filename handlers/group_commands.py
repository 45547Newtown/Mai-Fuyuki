# ============================================================
# Group Manager Bot
# ============================================================

from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated, ChatPermissions, ChatPrivileges, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus
import logging
import db

DEFAULT_WELCOME = "👋 Welcome {first_name} to {title}!"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def is_power(client, chat_id: int, user_id: int) -> bool:
    member = await client.get_chat_member(chat_id, user_id)
    return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]


async def extract_target_user(client, message):
    if message.reply_to_message:
        return message.reply_to_message.from_user
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return None
    arg = parts[1]
    try:
        if arg.startswith("@"):
            return await client.get_users(arg)
        elif arg.isdigit():
            return await client.get_users(int(arg))
    except:
        return None


async def handle_welcome(client, chat_id: int, users: list, chat_title: str):
    status = await db.get_welcome_status(chat_id)
    if not status:
        return

    welcome_text = await db.get_welcome_message(chat_id) or DEFAULT_WELCOME
    saved_buttons = await db.get_welcome_buttons(chat_id)

    reply_markup = None
    if saved_buttons:
        # Fix: sirf valid buttons use karo (empty text/url crash karta hai)
        valid_buttons = [btn for btn in saved_buttons if btn.get("text") and btn.get("url")]
        if valid_buttons:
            keyboard = [[InlineKeyboardButton(btn["text"], url=btn["url"])] for btn in valid_buttons]
            reply_markup = InlineKeyboardMarkup(keyboard)

    for user in users:
        try:
            text = welcome_text.format(
                username=user.username or user.first_name,
                first_name=user.first_name,
                mention=f"[{user.first_name}](tg://user?id={user.id})",
                title=chat_title,
            )
        except KeyError:
            text = DEFAULT_WELCOME.format(first_name=user.first_name, title=chat_title)

        try:
            await client.send_message(chat_id, text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Failed to send welcome: {e}")


def register_group_commands(app: Client):

    # welcome event
    @app.on_chat_member_updated()
    async def member_update(client: Client, cmu: ChatMemberUpdated):
        if not cmu.new_chat_member:
            return
        user = cmu.new_chat_member.user
        if cmu.new_chat_member.status == ChatMemberStatus.MEMBER:
            await handle_welcome(client, cmu.chat.id, [user], cmu.chat.title)

    # /welcome on/off
    @app.on_message(filters.group & filters.command("welcome"))
    async def welcome_toggle(client, message: Message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2 or parts[1].lower() not in ["on", "off"]:
            return await message.reply_text("Usage: /welcome on or /welcome off")
        status = parts[1].lower() == "on"
        await db.set_welcome_status(message.chat.id, status)
        await message.reply_text("✅ Welcome messages ON." if status else "⚠️ Welcome messages OFF.")

    # /setwelcome
    @app.on_message(filters.group & filters.command("setwelcome"))
    async def set_welcome(client, message: Message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply_text("Usage: /setwelcome <message>")
        await db.set_welcome_message(message.chat.id, parts[1])
        await message.reply_text("✅ Custom welcome saved!")

    # /setwelcomebutton
    @app.on_message(filters.group & filters.command("setwelcomebutton"))
    async def set_welcome_button(client, message: Message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply_text(
                "Usage:\n/setwelcomebutton Button Name | https://youtube.com\n\n"
                "Multiple buttons — har ek naye line pe:\n"
                "Main Channel | https://t.me/mychannel\n"
                "Support | https://t.me/support"
            )
        buttons = []
        errors = []
        for line in parts[1].strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if "|" not in line:
                errors.append(f"❌ `{line}` — '|' separator missing hai. Format: Name | URL")
                continue
            sp = line.split("|", 1)
            text = sp[0].strip()
            url = sp[1].strip()
            # Fix: text empty nahi hona chahiye
            if not text:
                errors.append(f"❌ Button name empty hai: `{line}`")
                continue
            # Fix: http aur tg:// dono valid hain
            if not (url.startswith("http://") or url.startswith("https://") or url.startswith("tg://")):
                errors.append(f"❌ Invalid URL `{url}` — https:// ya tg:// se shuru karo")
                continue
            buttons.append({"text": text, "url": url})
        if not buttons:
            err_msg = "⚠️ Koi valid button nahi mila.\n\n"
            err_msg += "✅ Sahi format:\n`/setwelcomebutton Main Channel | https://t.me/mychannel`\n\n"
            if errors:
                err_msg += "Errors:\n" + "\n".join(errors)
            return await message.reply_text(err_msg)
        await db.set_welcome_buttons(message.chat.id, buttons)
        btn_list = "\n".join([f"• {b['text']} → {b['url']}" for b in buttons])
        reply = f"✅ {len(buttons)} button(s) save ho gaye!\n\n{btn_list}"
        if errors:
            reply += "\n\n⚠️ Kuch lines skip hui:\n" + "\n".join(errors)
        await message.reply_text(reply)

    # /clearwelcomebutton
    @app.on_message(filters.group & filters.command("clearwelcomebutton"))
    async def clear_welcome_button(client, message: Message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        await db.clear_welcome_buttons(message.chat.id)
        await message.reply_text("🗑️ Welcome buttons hata diye gaye!")

    # /welcomebuttons
    @app.on_message(filters.group & filters.command("welcomebuttons"))
    async def show_welcome_buttons(client, message: Message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        saved = await db.get_welcome_buttons(message.chat.id)
        if not saved:
            return await message.reply_text("ℹ️ Koi welcome button set nahi hai.")
        btn_list = "\n".join([f"{i+1}. {b['text']} → {b['url']}" for i, b in enumerate(saved)])
        await message.reply_text(f"📋 Current buttons ({len(saved)}):\n\n{btn_list}")

    # /kick
    @app.on_message(filters.group & filters.command("kick"))
    async def kick_user(client, message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("Usage: Reply or /kick @username")
        target_member = await client.get_chat_member(message.chat.id, user.id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply_text("⚠️ Cannot kick admins.")
        if user.id == message.from_user.id:
            return await message.reply_text("⚠️ Cannot kick yourself.")
        try:
            await client.ban_chat_member(message.chat.id, user.id)
            await client.unban_chat_member(message.chat.id, user.id)
            await message.reply_text(f"👢 {user.mention} kicked.")
        except Exception as e:
            await message.reply_text(f"❌ Failed: {e}")

    # /ban
    @app.on_message(filters.group & filters.command("ban"))
    async def ban_user(client, message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("Usage: Reply or /ban @username")
        target_member = await client.get_chat_member(message.chat.id, user.id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply_text("⚠️ Cannot ban admins.")
        if user.id == message.from_user.id:
            return await message.reply_text("⚠️ Cannot ban yourself.")
        try:
            await client.ban_chat_member(message.chat.id, user.id)
            await message.reply_text(f"🚨 {user.mention} banned.")
        except Exception as e:
            await message.reply_text(f"❌ Failed: {e}")

    # /unban
    @app.on_message(filters.group & filters.command("unban"))
    async def unban_user(client, message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("Usage: Reply or /unban @username")
        try:
            await client.unban_chat_member(message.chat.id, user.id)
            await message.reply_text(f"✅ {user.mention} unbanned.")
        except Exception as e:
            await message.reply_text(f"❌ Failed: {e}")

    # /mute
    @app.on_message(filters.group & filters.command("mute"))
    async def mute_user(client, message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("Usage: Reply or /mute @username")
        target_member = await client.get_chat_member(message.chat.id, user.id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply_text("⚠️ Cannot mute admins.")
        if user.id == message.from_user.id:
            return await message.reply_text("⚠️ Cannot mute yourself.")
        try:
            await client.restrict_chat_member(message.chat.id, user.id, permissions=ChatPermissions(can_send_messages=False))
            await message.reply_text(f"🔇 {user.mention} muted.")
        except Exception as e:
            await message.reply_text(f"❌ Failed: {e}")

    # /unmute
    @app.on_message(filters.group & filters.command("unmute"))
    async def unmute_user(client, message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("Usage: Reply or /unmute @username")
        try:
            await client.restrict_chat_member(message.chat.id, user.id, permissions=ChatPermissions(
                can_send_messages=True, can_send_media_messages=True,
                can_send_other_messages=True, can_add_web_page_previews=True))
            await message.reply_text(f"🔊 {user.mention} unmuted.")
        except Exception as e:
            await message.reply_text(f"❌ Failed: {e}")

    # /warn
    @app.on_message(filters.group & filters.command("warn"))
    async def warn_user(client, message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("Usage: Reply or /warn @username")
        target_member = await client.get_chat_member(message.chat.id, user.id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply_text("⚠️ Cannot warn admins.")
        if user.id == message.from_user.id:
            return await message.reply_text("⚠️ Cannot warn yourself.")
        warns = await db.add_warn(message.chat.id, user.id)
        if warns >= 3:
            await client.restrict_chat_member(message.chat.id, user.id, permissions=ChatPermissions(can_send_messages=False))
            await message.reply_text(f"🚫 {user.mention} 3 warns — muted.")
        else:
            await message.reply_text(f"⚠️ {user.mention} {warns}/3 warnings.")

    # /warns
    @app.on_message(filters.group & filters.command("warns"))
    async def warns_user(client, message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("Usage: Reply or /warns @username")
        warns = await db.get_warns(message.chat.id, user.id)
        await message.reply_text(f"⚠️ {user.mention} has {warns}/3 warnings.")

    # /resetwarns
    @app.on_message(filters.group & filters.command("resetwarns"))
    async def resetwarns_user(client, message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("Usage: Reply or /resetwarns @username")
        await db.reset_warns(message.chat.id, user.id)
        await message.reply_text(f"✅ {user.mention} warns reset.")

    # /promote
    @app.on_message(filters.group & filters.command("promote"))
    async def promote_user(client: Client, message: Message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("Usage: Reply or /promote @username")
        target_member = await client.get_chat_member(message.chat.id, user.id)
        if target_member.status == ChatMemberStatus.OWNER:
            return await message.reply_text("⚠️ Cannot promote owner.")
        if user.id == message.from_user.id:
            return await message.reply_text("⚠️ Cannot promote yourself.")
        try:
            await client.promote_chat_member(chat_id=message.chat.id, user_id=user.id, privileges=ChatPrivileges(
                can_manage_chat=True, can_delete_messages=True, can_manage_video_chats=True,
                can_restrict_members=True, can_promote_members=False, can_change_info=True,
                can_invite_users=True, can_pin_messages=True, is_anonymous=False))
            await message.reply_text(f"✅ {user.mention} promoted to admin.")
        except Exception as e:
            await message.reply_text(f"❌ Failed: {e}")

    # /demote
    @app.on_message(filters.group & filters.command("demote"))
    async def demote_user(client: Client, message: Message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("Usage: Reply or /demote @username")
        try:
            target_member = await client.get_chat_member(message.chat.id, user.id)
        except Exception as e:
            return await message.reply_text(f"❌ Failed: {e}")
        if target_member.status == ChatMemberStatus.OWNER:
            return await message.reply_text("⚠️ Cannot demote owner.")
        if target_member.status != ChatMemberStatus.ADMINISTRATOR:
            return await message.reply_text("⚠️ User is not an admin.")
        if user.id == message.from_user.id:
            return await message.reply_text("⚠️ Cannot demote yourself.")
        try:
            await client.promote_chat_member(chat_id=message.chat.id, user_id=user.id, privileges=ChatPrivileges(
                can_manage_chat=False, can_delete_messages=False, can_manage_video_chats=False,
                can_restrict_members=False, can_promote_members=False, can_change_info=False,
                can_invite_users=False, can_pin_messages=False, is_anonymous=False))
            await message.reply_text(f"✅ {user.mention} demoted.")
        except Exception as e:
            await message.reply_text(f"❌ Failed: {e}")
