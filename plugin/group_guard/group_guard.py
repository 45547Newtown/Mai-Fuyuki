from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

LOG_CHANNEL = -1003924212087  # apna LOG CHANNEL id


def register_group_guard(app):

    @app.on_message(filters.new_chat_members & filters.group, group=-200)
    async def group_add_request(client, message):
        me = await client.get_me()

        for user in message.new_chat_members:
            if user.id == me.id:
                group_id = message.chat.id
                group_title = message.chat.title
                added_by = message.from_user

                text = f"""🚨 Bot Added To New Group

👥 Group: {group_title}
🆔 Group ID: `{group_id}`

👤 Added By: {added_by.first_name}
🆔 User ID: `{added_by.id}`

Accept or Reject this group?"""

                buttons = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Accept", callback_data=f"gg_accept:{group_id}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"gg_reject:{group_id}")
                    ]
                ])

                await client.send_message(LOG_CHANNEL, text, reply_markup=buttons)

    @app.on_callback_query(filters.regex("^gg_accept:"))
    async def accept_group(client, query):
        group_id = int(query.data.split(":")[1])
        await query.message.edit_text(f"✅ Group Accepted\n\nGroup ID: `{group_id}`")
        await query.answer("Accepted")

    @app.on_callback_query(filters.regex("^gg_reject:"))
    async def reject_group(client, query):
        group_id = int(query.data.split(":")[1])

        try:
            await client.leave_chat(group_id)
        except Exception as e:
            await query.answer(f"Leave failed: {e}", show_alert=True)
            return

        await query.message.edit_text(f"❌ Group Rejected\n\nBot left group: `{group_id}`")
        await query.answer("Rejected")
