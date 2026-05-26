# ============================================================
# Group Manager Bot
# Author: LearningBotsOfficial (https://github.com/LearningBotsOfficial) 
# Support: https://t.me/LearningBotsCommunity
# Channel: https://t.me/learning_bots
# YouTube: https://youtube.com/@learning_bots
# License: Open-source (keep credits, no resale)
# ============================================================

from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated, ChatPermissions, ChatPrivileges, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus
from pyrogram.raw import types
import logging
import db

DEFAULT_WELCOME = "👋 Welcome {first_name} to {title}!"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)



# ==========================================================
# Global helper
# ==========================================================

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

    # Build inline keyboard if buttons are saved
    reply_markup = None
    if saved_buttons:
        keyboard = []
        for btn in saved_buttons:
            keyboard.append([InlineKeyboardButton(btn["text"], url=btn["url"])])
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
            logger.error(f"🚨 Failed to send welcome message: {e}")




def register_group_commands(app: Client):

    # ==========================================================
    # welcome event
    # ==========================================================
    
    @app.on_chat_member_updated()
    async def member_update(client: Client, cmu: ChatMemberUpdated):
    
        if not cmu.new_chat_member:
            return
    
        user = cmu.new_chat_member.user
        new_status = cmu.new_chat_member.status
    
        if new_status == ChatMemberStatus.MEMBER:
    
            await handle_welcome(
                client,
                cmu.chat.id,
                [user],
                cmu.chat.title,
            )
    
    
    # ==========================================================
    # welcome toggle
    # ==========================================================
    
    @app.on_message(filters.group & filters.command("welcome"))
    async def welcome_toggle(client, message: Message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin or owner can use this command.")
    
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2 or parts[1].lower() not in ["on", "off"]:
            return await message.reply_text("⚙️ Usage: /welcome on/off")
    
        status = parts[1].lower() == "on"
        await db.set_welcome_status(message.chat.id, status)
    
        await message.reply_text(
            "✅ Welcome messages ON." if status else "⚠️ Welcome messages OFF."
        )
    
    
    # ==========================================================
    # set welcome
    # ========================================================== 
    
    @app.on_message(filters.group & filters.command("setwelcome"))
    async def set_welcome(client, message: Message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("⚠️ Only admin can use this command.")
    
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply_text("🤖 Usage: /setwelcome <message>")
    
        await db.set_welcome_message(message.chat.id, parts[1])
        await message.reply_text("✅ Custom welcome saved!")


    # ==========================================================
    # setwelcomebutton
    # Usage: /setwelcomebutton YouTube Channel | https://youtube.com
    #        Multiple buttons: har ek naye line pe
    # ==========================================================

    @app.on_message(filters.group & filters.command("setwelcomebutton"))
    async def set_welcome_button(client, message: Message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")

        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply_text(
                "📌 Usage:\n"
                "`/setwelcomebutton Button Name | https://link.com`\n\n"
                "Multiple buttons:\n"
                "`/setwelcomebutton YouTube Channel | https://youtube.com\n"
                "Tutorial Channel | https://t.me/channel`"
            )

        buttons = []
        errors = []
        for line in parts[1].strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if "|" not in line:
                errors.append(f"❌ `{line}` — `|` missing")
                continue
            split = line.split("|", 1)
            text = split[0].strip()
            url = split[1].strip()
            if not url.startswith("http"):
                errors.append(f"❌ Invalid URL: `{url}`")
                continue
            buttons.append({"text": text, "url": url})

        if not buttons:
            return await message.reply_text("⚠️ Koi valid button nahi mila.\nFormat: `Name | https://link.com`")

        await db.set_welcome_buttons(message.chat.id, buttons)
        btn_list = "\n".join([f"• {b['text']} → {b['url']}" for b in buttons])
        reply = f"✅ {len(buttons)} button(s) save ho gaye!\n\n{btn_list}"
        if errors:
            reply += "\n\n" + "\n".join(errors)
        await message.reply_text(reply)


    # ==========================================================
    # clearwelcomebutton
    # ==========================================================

    @app.on_message(filters.group & filters.command("clearwelcomebutton"))
    async def clear_welcome_button(client, message: Message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        await db.clear_welcome_buttons(message.chat.id)
        await message.reply_text("🗑️ Welcome buttons hata diye gaye!")


    # ==========================================================
    # welcomebuttons — current buttons dekho
    # ==========================================================

    @app.on_message(filters.group & filters.command("welcomebuttons"))
    async def show_welcome_buttons(client, message: Message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
        saved = await db.get_welcome_buttons(message.chat.id)
        if not saved:
            return await message.reply_text("ℹ️ Koi welcome button set nahi hai.")
        btn_list = "\n".join([f"{i+1}. {b['text']} → {b['url']}" for i, b in enumerate(saved)])
        await message.reply_text(f"📋 Current buttons ({len(saved)}):\n\n{btn_list}")


    
    # ==========================================================
    # kick
    # ==========================================================
    @app.on_message(filters.group & filters.command("kick"))
    async def kick_user(client, message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
    
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("⚠️ Usage: Reply or use `/kick @username`")
    
        target_member = await client.get_chat_member(message.chat.id, user.id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply_text("⚠️ Cannot perform action on admins.")
        if user.id == message.from_user.id:
            return await message.reply_text("⚠️ You cannot kick yourself.")
    
        try:
            await client.ban_chat_member(message.chat.id, user.id)
            await client.unban_chat_member(message.chat.id, user.id)
            await message.reply_text(f"👢 {user.mention} has been kicked.")
        except Exception as e:
            await message.reply_text(f"❌ Failed to kick: {e}")
    
    
    # ==========================================================
    # ban
    # ==========================================================
    @app.on_message(filters.group & filters.command("ban"))
    async def ban_user(client, message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
    
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("⚠️ Usage: Reply or use `/ban @username`")
    
        target_member = await client.get_chat_member(message.chat.id, user.id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply_text("⚠️ Cannot perform action on admins.")
        if user.id == message.from_user.id:
            return await message.reply_text("⚠️ You cannot ban yourself.")
    
        try:
            await client.ban_chat_member(message.chat.id, user.id)
            await message.reply_text(f"🚨 {user.mention} has been banned.")
        except Exception as e:
            await message.reply_text(f"❌ Failed to ban: {e}")
    
    
    # ==========================================================
    # unban
    # ==========================================================
    @app.on_message(filters.group & filters.command("unban"))
    async def unban_user(client, message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
    
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("⚠️ Usage: Reply or use `/unban @username`")
    
        target_member = await client.get_chat_member(message.chat.id, user.id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply_text("⚠️ Cannot perform action on admins.")
        if user.id == message.from_user.id:
            return await message.reply_text("⚠️ You cannot unban yourself.")
    
        try:
            await client.unban_chat_member(message.chat.id, user.id)
            await message.reply_text(f"✅ {user.mention} has been unbanned.")
        except Exception as e:
            await message.reply_text(f"❌ Failed to unban: {e}")
    
    
    # ==========================================================
    # mute
    # ==========================================================
    @app.on_message(filters.group & filters.command("mute"))
    async def mute_user(client, message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
    
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("⚠️ Usage: Reply or use `/mute @username`")
    
        target_member = await client.get_chat_member(message.chat.id, user.id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply_text("⚠️ Cannot perform action on admins.")
        if user.id == message.from_user.id:
            return await message.reply_text("⚠️ You cannot mute yourself.")
    
        try:
            await client.restrict_chat_member(
                message.chat.id,
                user.id,
                permissions=ChatPermissions(can_send_messages=False),
            )
            await message.reply_text(f"🔇 {user.mention} has been muted.")
        except Exception as e:
            await message.reply_text(f"❌ Failed to mute: {e}")
    
    
    # ==========================================================
    # unmute
    # ==========================================================
    @app.on_message(filters.group & filters.command("unmute"))
    async def unmute_user(client, message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
    
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("⚠️ Usage: Reply or use `/unmute @username`")
    
        target_member = await client.get_chat_member(message.chat.id, user.id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply_text("⚠️ Cannot perform action on admins.")
        if user.id == message.from_user.id:
            return await message.reply_text("⚠️ You cannot unmute yourself.")
    
        try:
            await client.restrict_chat_member(
                message.chat.id,
                user.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
            )
            await message.reply_text(f"🔊 {user.mention} has been unmuted.")
        except Exception as e:
            await message.reply_text(f"❌ Failed to unmute: {e}")
    
    
    # ==========================================================
    # warn
    # ==========================================================
    @app.on_message(filters.group & filters.command("warn"))
    async def warn_user(client, message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
    
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("⚠️ Usage: Reply or use `/warn @username`")
    
        target_member = await client.get_chat_member(message.chat.id, user.id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply_text("⚠️ Cannot warn admins.")
        if user.id == message.from_user.id:
            return await message.reply_text("⚠️ You cannot warn yourself.")
    
        warns = await db.add_warn(message.chat.id, user.id)
        if warns >= 3:
            await client.restrict_chat_member(
                message.chat.id,
                user.id,
                permissions=ChatPermissions(can_send_messages=False),
            )
            await message.reply_text(f"🚫 {user.mention} reached 3 warns and was muted.")
        else:
            await message.reply_text(f"⚠️ {user.mention} now has {warns}/3 warnings.")
    
    
    # ==========================================================
    # warns
    # ==========================================================
    @app.on_message(filters.group & filters.command("warns"))
    async def warns_user(client, message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
    
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("⚠️ Usage: Reply or use `/warns @username`")
    
        target_member = await client.get_chat_member(message.chat.id, user.id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply_text("⚠️ Cannot check warns for admins.")
    
        warns = await db.get_warns(message.chat.id, user.id)
        await message.reply_text(f"⚠️ {user.mention} has {warns}/3 warnings.")
    
    
    # ==========================================================
    # resetwarns
    # ==========================================================
    @app.on_message(filters.group & filters.command("resetwarns"))
    async def resetwarns_user(client, message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
    
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("⚠️ Usage: Reply or use `/resetwarns @username`")
    
        target_member = await client.get_chat_member(message.chat.id, user.id)
        if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply_text("⚠️ Cannot reset warns for admins.")
    
        await db.reset_warns(message.chat.id, user.id)
        await message.reply_text(f"✅ {user.mention}'s warns have been reset.")
          
    
          
    # ==========================================================
    # Promote Command
    # ==========================================================
    @app.on_message(filters.group & filters.command("promote"))
    async def promote_user(client: Client, message: Message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin or owner can use this command.")
    
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("⚠️ Usage: Reply to a user or use '/promote @username'")
    
        target_member = await client.get_chat_member(message.chat.id, user.id)
    
        if target_member.status == ChatMemberStatus.OWNER:
            return await message.reply_text("⚠️ Cannot promote the group owner.")
    
        if user.id == message.from_user.id:
            return await message.reply_text("⚠️ You cannot promote yourself.")
    
        try:
            privileges = ChatPrivileges(
                can_manage_chat=True,
                can_delete_messages=True,
                can_manage_video_chats=True,
                can_restrict_members=True,
                can_promote_members=False,
                can_change_info=True,
                can_invite_users=True,
                can_pin_messages=True,
                can_post_messages=False,
                can_edit_messages=False,
                is_anonymous=False
            )
    
            await client.promote_chat_member(
                chat_id=message.chat.id,
                user_id=user.id,
                privileges=privileges
            )
            await message.reply_text(f"✅ {user.mention} has been promoted to admin.")
    
        except Exception as e:
            if "USER_NOT_PARTICIPANT" in str(e):
                await message.reply_text("⚠️ Cannot promote: user is not a member of this chat.")
            elif "CHAT_ADMIN_REQUIRED" in str(e):
                await message.reply_text("⚠️ Bot must be admin with 'Add Admins' permission to promote.")
            else:
                await message.reply_text(f"❌ Failed to promote: {e}")
        
        
    # ==========================================================
    # Demote Command
    # ==========================================================
    @app.on_message(filters.group & filters.command("demote"))
    async def demote_user(client: Client, message: Message):
        if not await is_power(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Only admin can use this command.")
    
        user = await extract_target_user(client, message)
        if not user:
            return await message.reply_text("⚠️ Usage: Reply to a user or use '/demote @username'")
    
        try:
            target_member = await client.get_chat_member(message.chat.id, user.id)
        except Exception as e:
            if "USER_NOT_PARTICIPANT" in str(e):
                return await message.reply_text("❌ Cannot demote: user is not a member of this chat.")
            return await message.reply_text(f"⚠️ Failed to demote: {e}")
    
        if target_member.status == ChatMemberStatus.OWNER:
            return await message.reply_text("⚠️ You cannot demote the group owner.")
    
        if target_member.status not in [ChatMemberStatus.ADMINISTRATOR]:
            return await message.reply_text("⚠️ User is not an admin.")
    
        if user.id == message.from_user.id:
            return await message.reply_text("❌ You cannot demote yourself.")
    
        try:
            no_privileges = ChatPrivileges(
                can_manage_chat=False,
                can_delete_messages=False,
                can_manage_video_chats=False,
                can_restrict_members=False,
                can_promote_members=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
                can_post_messages=False,
                can_edit_messages=False,
                is_anonymous=False
            )
    
            await client.promote_chat_member(
                chat_id=message.chat.id,
                user_id=user.id,
                privileges=no_privileges
            )
            await message.reply_text(f"✅ {user.mention} has been demoted from admin.")
    
        except Exception as e:
            if "CHAT_ADMIN_REQUIRED" in str(e):
                await message.reply_text("❌ Bot must be admin with 'Add Admins' permission to demote.")
            else:
                await message.reply_text(f"⚠️ Failed to demote: {e}")
        