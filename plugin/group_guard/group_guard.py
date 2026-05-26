from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus

LOG_CHANNEL = -1001234567890  # apna log channel id

pending_groups = {}


@Client.on_my_chat_member()
async def group_add_handler(client, update):

    chat = update.chat

    if chat.type not in ["group", "supergroup"]:
        return

    old_status = update.old_chat_member.status
    new_status = update.new_chat_member.status

    if old_status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED] and \
       new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:

        pending_groups[chat.id] = chat.id

        text = f"""
🚨 New Group Add Request

🏷 Group Name: {chat.title}
🆔 Group ID: `{chat.id}`

Do you want to approve this group?
"""

        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Accept",
                    callback_data=f"approve_{chat.id}"
                ),
                InlineKeyboardButton(
                    "❌ Reject",
                    callback_data=f"reject_{chat.id}"
                )
            ]
        ])

        await client.send_message(
            LOG_CHANNEL,
            text,
            reply_markup=buttons
        )


@Client.on_callback_query(filters.regex("^approve_"))
async def approve_group(client, callback_query):

    group_id = int(callback_query.data.split("_")[1])

    if group_id in pending_groups:
        del pending_groups[group_id]

    await callback_query.message.edit_text(
        f"✅ Group Approved\n\n🆔 `{group_id}`"
    )

    await callback_query.answer("Approved")


@Client.on_callback_query(filters.regex("^reject_"))
async def reject_group(client, callback_query):

    group_id = int(callback_query.data.split("_")[1])

    try:
        await client.leave_chat(group_id)
    except:
        pass

    if group_id in pending_groups:
        del pending_groups[group_id]

    await callback_query.message.edit_text(
        f"❌ Group Rejected\n\n🆔 `{group_id}`"
    )

    await callback_query.answer("Rejected")
