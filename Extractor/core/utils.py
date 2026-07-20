from datetime import datetime
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from config import CHANNEL_ID
from Extractor import app

async def forward_to_log(message: Message, module_name: str):
    try:
        channel = CHANNEL_ID if isinstance(CHANNEL_ID, int) else int(CHANNEL_ID)
        raw_id = str(abs(channel))

        log_text = "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        log_text += f"👤 {message.from_user.first_name}"
        if message.from_user.username:
            log_text += f" (@{message.from_user.username})"
        log_text += f" [{message.from_user.id}]\n\n"

        log_text += f"📱 Module: {module_name}\n"
        log_text += f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}\n\n"

        log_text += f"💬 Message:\n**{message.text}**\n"
        log_text += "\n━━━━━━━━━━━━━━━━━━━━━━"

        try:
            await app.send_message(
                chat_id=channel,
                text=log_text,
                parse_mode=ParseMode.HTML
            )
        except Exception as e1:
            try:
                await app.send_message(
                    chat_id=int(f"-100{raw_id}"),
                    text=log_text,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e2:
                print(f"Error with original channel ID: {e1}")
                print(f"Error with modified channel ID: {e2}")
                print(f"Channel ID attempted: {channel} and -100{raw_id}")
                raise

    except Exception as e:
        print(f"Error forwarding to log channel: {e}")
        print(f"Message: {message.text if message.text else 'No text'}")
        print(f"From user: {message.from_user.first_name} [{message.from_user.id}]")
        print(f"Module: {module_name}")
        print(f"Channel ID: {CHANNEL_ID}")