import os
from dotenv import load_dotenv
import asyncio
import threading
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

from settings import setup_extra_handlers, load_initial_settings, is_admin, DEFAULT_ADMINS
from settings import get_all_target_channels, add_target_channel, remove_target_channel
from angel_db import is_forwarded_for_target, mark_as_forwarded_for_target
from angel_db import collection, settings_col

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
STATUS_URL = os.getenv("STATUS_URL")
SOURCE_CHAT_ID = int(os.getenv("SOURCE_CHAT_ID"))
PORT = int(os.getenv("PORT", 8080))

# ===== LOAD SESSION FROM MONGODB (Render Safe) =====
session_data = settings_col.find_one({"key": "session"})
if session_data:
    woodcraft = TelegramClient(StringSession(session_data["value"]), API_ID, API_HASH)
else:
    woodcraft = TelegramClient(StringSession(), API_ID, API_HASH)

woodcraft.delay_seconds = 5
woodcraft.skip_next_message = False
app = Flask(__name__)
forwarding_enabled = True

# ================= LOGIN VIA SAVED MESSAGES =================
login_state = {}

@woodcraft.on(events.NewMessage(pattern=r'^/login$', from_users='me'))
async def login_start(event):
    login_state["step"] = "phone"
    await event.reply("📱 Phone number bhejo country code ke sath. Example: +919876543210")

@woodcraft.on(events.NewMessage(from_users='me'))
async def login_flow(event):
    if "step" not in login_state:
        return

    if login_state["step"] == "phone":
        phone = event.text.strip()
        login_state["phone"] = phone
        await woodcraft.send_code_request(phone)
        login_state["step"] = "otp"
        await event.reply("🔐 OTP bhejo")

    elif login_state["step"] == "otp":
        otp = event.text.strip()
        try:
            await woodcraft.sign_in(login_state["phone"], otp)

            # ✅ SAVE SESSION TO MONGODB
            session_str = woodcraft.session.save()
            settings_col.update_one(
                {"key": "session"},
                {"$set": {"value": session_str}},
                upsert=True
            )

            await event.reply("✅ Login successful! Session MongoDB me save ho gaya.")
            login_state.clear()

        except Exception as e:
            await event.reply(f"❌ Error: {e}")

# ================= REST OF YOUR ORIGINAL CODE SAME =================
async def send_without_tag(original_msg):
    try:
        targets = await get_all_target_channels()
        if not targets:
            print("⚠️ There is no target channel!")
            return False

        for target in targets:
            if await is_forwarded_for_target(original_msg.id, target):
                continue

            if original_msg.media:
                await woodcraft.send_file(
                    entity=target,
                    file=original_msg.media,
                    caption=original_msg.text,
                    silent=True
                )
            else:
                await woodcraft.send_message(
                    entity=target,
                    message=original_msg.text,
                    formatting_entities=original_msg.entities,
                    silent=True
                )

            await mark_as_forwarded_for_target(original_msg.id, target)
            await asyncio.sleep(woodcraft.delay_seconds)

    except FloodWaitError as e:
        await asyncio.sleep(e.seconds + 5)
        await send_without_tag(original_msg)

@woodcraft.on(events.NewMessage(pattern=r'^/status$'))
async def status(event):
    if not is_admin(event.sender_id):
        return

    total_forwarded_files = collection.count_documents({})
    await woodcraft.send_file(
        event.chat_id,
        file=STATUS_URL,
        caption=f"Forwarded: `{total_forwarded_files}`",
        parse_mode='md'
    )

@woodcraft.on(events.NewMessage(chats=SOURCE_CHAT_ID))
async def new_message_handler(event):
    global forwarding_enabled
    if forwarding_enabled and not woodcraft.skip_next_message:
        await asyncio.sleep(woodcraft.delay_seconds)
        await send_without_tag(event.message)

@app.route("/")
def home():
    return "🤖 Angel Userbot Running", 200

async def main():
    await woodcraft.start()
    print("✅ Bot started")
    await load_initial_settings(woodcraft)
    setup_extra_handlers(woodcraft)
    await woodcraft.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": PORT}).start()
    asyncio.run(main())
