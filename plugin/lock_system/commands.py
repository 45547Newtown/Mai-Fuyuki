from pyrogram import filters
from pyrogram.types import ChatPermissions

VALID_LOCKS = ["url", "sticker", "media", "username", "forward"]


async def is_admin(client, chat_id, user_id):
    member = await client.get_chat_member(chat_id, user_id)
    return member.status in ("administrator", "owner")


def register_lock_system(app):

    @app.on_message(filters.command("lock") & filters.group)
    async def lock_cmd(client, message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("Only admins can use this command.")

        if len(message.command) < 2:
            return await message.reply_text(
                "⚠️ Available: url, sticker, media, username, forward, all"
            )

        lock_type = message.command[1].lower()

        if lock_type == "all":
            await client.set_chat_permissions(
                message.chat.id,
                ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                    can_send_polls=False,
                    can_invite_users=True,
                ),
            )
            return await message.reply_text("Locked all.")

        if lock_type not in VALID_LOCKS:
            return await message.reply_text(
                "⚠️ Available: url, sticker, media, username, forward"
            )

        return await message.reply_text(f"Locked {lock_type}.")

    @app.on_message(filters.command("unlock") & filters.group)
    async def unlock_cmd(client, message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("Only admins can use this command.")

        if len(message.command) < 2:
            return await message.reply_text(
                "⚠️ Available: url, sticker, media, username, forward, all"
            )

        lock_type = message.command[1].lower()

        if lock_type == "all":
            await client.set_chat_permissions(
                message.chat.id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_send_polls=True,
                    can_invite_users=True,
                ),
            )
            return await message.reply_text("Unlocked all.")

        if lock_type not in VALID_LOCKS:
            return await message.reply_text(
                "⚠️ Available: url, sticker, media, username, forward"
            )

        return await message.reply_text(f"Unlocked {lock_type}.")
