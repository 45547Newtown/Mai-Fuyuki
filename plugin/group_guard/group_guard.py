# ============================================================
# Group Manager Bot
# Author: LearningBotsOfficial (https://github.com/LearningBotsOfficial)
# ============================================================

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import LOG_CHAT_ID
import db
import logging

logger = logging.getLogger(__name__)


def register_group_guard(app):

    # ----------------------------------------------------------
    # Jab bot kisi group mein add ho
    # ----------------------------------------------------------
    @app.on_message(filters.new_chat_members & filters.group, group=-200)
    async def group_add_request(client, message):
        me = await client.get_me()

        for user in message.new_chat_members:
            if user.id == me.id:
                group_id = message.chat.id
                group_title = message.chat.title or "Unknown Group"
                added_by = message.from_user

                # Group ko "pending" mark karo
                await db.set_group_status(group_id, "pending")

                if not LOG_CHAT_ID:
                    logger.warning("⚠️ LOG_CHAT_ID not set — group guard notification skipped.")
                    return

                added_name = added_by.first_name if added_by else "Unknown"
                added_id = added_by.id if added_by else "N/A"

                text = (
                    "🔔 <b>Bot Nayi Group Mein Add Hua</b>\n\n"
                    f"👥 <b>Group:</b> {group_title}\n"
                    f"🆔 <b>Group ID:</b> <code>{group_id}</code>\n\n"
                    f"👤 <b>Add Kiya:</b> {added_name}\n"
                    f"🆔 <b>User ID:</b> <code>{added_id}</code>\n\n"
                    "⚠️ <i>Jab tak approve nahi hoga, commands kaam nahi karengi.</i>\n\n"
                    "Is group ko approve ya reject karein?"
                )

                buttons = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Confirm", callback_data=f"gg_accept:{group_id}"),
                        InlineKeyboardButton("❌ Decline", callback_data=f"gg_reject:{group_id}"),
                    ]
                ])

                try:
                    await client.send_message(
                        LOG_CHAT_ID,
                        text,
                        reply_markup=buttons,
                        parse_mode="html",
                    )
                except Exception as e:
                    logger.error(f"❌ Log channel mein message nahi bheja ja saka: {e}")

    # ----------------------------------------------------------
    # ✅ Confirm button
    # ----------------------------------------------------------
    @app.on_callback_query(filters.regex(r"^gg_accept:(-?\d+)$"))
    async def accept_group(client, query):
        group_id = int(query.data.split(":")[1])
        await db.set_group_status(group_id, "approved")

        try:
            await client.send_message(
                group_id,
                "✅ <b>Group approve ho gayi!</b>\n\nAb sab commands available hain. 🎉",
                parse_mode="html",
            )
        except Exception as e:
            logger.warning(f"Group ko notify nahi kar saka: {e}")

        await query.message.edit_text(
            f"✅ <b>Group Approved</b>\n\n"
            f"🆔 Group ID: <code>{group_id}</code>\n"
            f"👮 Approved by: {query.from_user.mention}",
            parse_mode="html",
        )
        await query.answer("✅ Group approve ho gayi!")

    # ----------------------------------------------------------
    # ❌ Decline button
    # ----------------------------------------------------------
    @app.on_callback_query(filters.regex(r"^gg_reject:(-?\d+)$"))
    async def reject_group(client, query):
        group_id = int(query.data.split(":")[1])

        try:
            await client.send_message(
                group_id,
                "❌ <b>Maafi chahte hain!</b>\n\nIs group ko approve nahi kiya gaya. Bot ab group chhod raha hai.",
                parse_mode="html",
            )
        except Exception:
            pass

        try:
            await client.leave_chat(group_id)
        except Exception as e:
            await query.answer(f"Leave nahi ho saka: {e}", show_alert=True)
            return

        await db.set_group_status(group_id, "rejected")

        await query.message.edit_text(
            f"❌ <b>Group Rejected</b>\n\n"
            f"🆔 Group ID: <code>{group_id}</code>\n"
            f"👮 Rejected by: {query.from_user.mention}\n"
            f"🚪 Bot group chhod gaya.",
            parse_mode="html",
        )
        await query.answer("❌ Group reject ho gayi aur bot chala gaya.")
        
