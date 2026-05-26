from pyrogram import filters

LOCKED_URL = set()


def register_lock_url(app):

    @app.on_message(filters.command("lock") & filters.group)
    async def lock_url_cmd(client, message):
        if len(message.command) > 1 and message.command[1].lower() == "url":
            LOCKED_URL.add(message.chat.id)
            await message.reply_text("🔒 Locked url.")

    @app.on_message(filters.command("unlock") & filters.group)
    async def unlock_url_cmd(client, message):
        if len(message.command) > 1 and message.command[1].lower() == "url":
            LOCKED_URL.discard(message.chat.id)
            await message.reply_text("🔓 Unlocked url.")

    @app.on_message(filters.group & (filters.text | filters.caption))
    async def delete_url(client, message):
        text = message.text or message.caption or ""

        if message.chat.id in LOCKED_URL:
            if (
                "http://" in text
                or "https://" in text
                or "t.me/" in text
                or ".com" in text
            ):
                try:
                    await message.delete()
                except:
                    pass
