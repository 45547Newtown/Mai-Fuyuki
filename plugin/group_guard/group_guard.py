from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

LOG_CHANNEL = -1001234567890  # your log channel id


def register_group_guard(app):

    @app.on_message(filters.new_chat_members & filters.group)
    async def bot_added(client, message):

        for member in message.new_chat_members:

            if member.is_self:

                text = f"""
🚨 New Group Add Request

🏷 Group Name: {message.chat.title}
🆔 Group ID: `{message.chat.id}`

Approve this group?
"""

                buttons = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "✅ Accept",
                                callback_data=f"approve_{message.chat.id}"
                            ),
                            InlineKeyboardButton(
                                "❌ Reject",
                                callback_data=f"reject_{message.chat.id}"
                            )
                        ]
                    ]
                )

                await client.send_message(
                    LOG_CHANNEL,
                    text,
                    reply_markup=buttons
                )

    @app.on_callback_query(filters.regex("^approve_"))
    async def approve_group(client, callback_query):

        group_id = callback_query.data.split("_")[1]

        await callback_query.message.edit_text(
            f"✅ Group Approved\n\n🆔 `{group_id}`"
        )

        await callback_query.answer("Approved")

    @app.on_callback_query(filters.regex("^reject_"))
    async def reject_group(client, callback_query):

        group_id = int(callback_query.data.split("_")[1])

        try:
            await client.leave_chat(group_id)
        except:
            pass

        await callback_query.message.edit_text(
            f"❌ Group Rejected\n\n🆔 `{group_id}`"
        )

        await callback_query.answer("Rejected")
