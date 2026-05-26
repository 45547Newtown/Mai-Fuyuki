from pyrogram import filters

LOCKED_STICKER = set()


def register_lock_sticker(app):

    @app.on_message(filters.command("lock") & filters.group)
    async def lock_sticker_cmd(client, message):
        if len(message.command) > 1 and message.command[1].lower() == "sticker":
            LOCKED_STICKER.add(message.chat.id)
            await message.reply_text("🔒 Locked sticker.")

    @app.on_message(filters.command("unlock") & filters.group)
    async def unlock_sticker_cmd(client, message):
        if len(message.command) > 1 and message.command[1].lower() == "sticker":
            LOCKED_STICKER.discard(message.chat.id)
            await message.reply_text("🔓 Unlocked sticker.")

    @app.on_message(filters.group & filters.sticker)
    async def delete_sticker(client, message):
        if message.chat.id in LOCKED_STICKER:
            try:
                await message.delete()
            except:
                pass
