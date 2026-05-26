from pyrogram import filters
from pyrogram.types import ChatPrivileges

WELCOME_STATUS = {}
WELCOME_TEXT = {}


def register_welcome_system(app):

    @app.on_message(filters.command("welcome") & filters.group)
    async def toggle_welcome(client, message):

        member = await client.get_chat_member(
            message.chat.id,
            message.from_user.id
        )

        if not (
            member.privileges
            and member.privileges.can_manage_chat
        ):
            return await message.reply_text(
                "Only admins can use this command."
            )

        if len(message.command) < 2:
            return await message.reply_text(
                "Usage:\n/welcome on\n/welcome off"
            )

        option = message.command[1].lower()

        if option == "on":
            WELCOME_STATUS[message.chat.id] = True
            return await message.reply_text(
                "✅ Welcome enabled."
            )

        elif option == "off":
            WELCOME_STATUS[message.chat.id] = False
            return await message.reply_text(
                "❌ Welcome disabled."
            )

    @app.on_message(filters.command("setwelcome") & filters.group)
    async def set_welcome(client, message):

        member = await client.get_chat_member(
            message.chat.id,
            message.from_user.id
        )

        if not (
            member.privileges
            and member.privileges.can_manage_chat
        ):
            return await message.reply_text(
                "Only admins can use this command."
            )

        text = message.text.split(None, 1)

        if len(text) < 2:
            return await message.reply_text(
                "Usage:\n/setwelcome Welcome {first_name}"
            )

        WELCOME_TEXT[message.chat.id] = text[1]

        await message.reply_text(
            "✅ Welcome message updated."
        )

    @app.on_message(filters.new_chat_members)
    async def welcome_new_member(client, message):

        if not WELCOME_STATUS.get(message.chat.id):
            return

        template = WELCOME_TEXT.get(
            message.chat.id,
            "Hello {first_name}, welcome to {title}!"
        )

        for user in message.new_chat_members:

            text = template.format(
                first_name=user.first_name,
                username=user.username or "NoUsername",
                id=user.id,
                mention=user.mention,
                title=message.chat.title
            )

            await message.reply_text(text)
