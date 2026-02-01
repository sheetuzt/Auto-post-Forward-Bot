import os
import asyncio
import threading
from flask import Flask
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError

from settings import setup_extra_handlers, load_initial_settings, is_admin
from settings import get_all_target_channels, add_target_channel, remove_target_channel
from angel_db import is_forwarded_for_target, mark_as_forwarded_for_target, collection

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
STATUS_URL = os.getenv("STATUS_URL")
SOURCE_CHAT_ID = int(os.getenv("SOURCE_CHAT_ID"))
PORT = int(os.getenv("PORT", 8080))

# ===== USERBOT SESSION (no StringSession) =====
woodcraft = TelegramClient("userbot", API_ID, API_HASH)
app = Flask(__name__)

forwarding_enabled = True
login_state = {}

# ================= LOGIN VIA SAVED MESSAGES =================
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
            await event.reply("✅ Login successful! Session file save ho gayi.")
            login_state.clear()
        except Exception as e:
            await event.reply(f"❌ Error: {e}")

# ================= FORWARD FUNCTION =================
async def send_without_tag(original_msg):
    try:
        targets = await get_all_target_channels()
        for target in targets:
            if await is_forwarded_for_target(original_msg.id, target):
                continue

            if original_msg.media:
                await woodcraft.send_file(
                    target,
                    file=original_msg.media,
                    caption=original_msg.text,
                    silent=True
                )
            else:
                await woodcraft.send_message(
                    target,
                    original_msg.text,
                    formatting_entities=original_msg.entities,
                    silent=True
                )

            await mark_as_forwarded_for_target(original_msg.id, target)
            await asyncio.sleep(woodcraft.delay_seconds)

    except FloodWaitError as e:
        await asyncio.sleep(e.seconds + 5)
        await send_without_tag(original_msg)

# ================= COMMANDS =================
@woodcraft.on(events.NewMessage(pattern=r'^/status$'))
async def status(event):
    if not is_admin(event.sender_id):
        return
    total = collection.count_documents({})
    await woodcraft.send_file(
        event.chat_id,
        STATUS_URL,
        caption=f"Forwarded: `{total}`\nDelay: `{woodcraft.delay_seconds}s`",
        parse_mode='md'
    )

@woodcraft.on(events.NewMessage(chats=SOURCE_CHAT_ID))
async def new_message_handler(event):
    global forwarding_enabled
    if forwarding_enabled and not woodcraft.skip_next_message:
        await asyncio.sleep(woodcraft.delay_seconds)
        await send_without_tag(event.message)

# ================= WEB =================
@app.route("/")
def home():
    return "Userbot Running", 200

# ================= MAIN =================
async def main():
    await woodcraft.start()
    await load_initial_settings(woodcraft)
    setup_extra_handlers(woodcraft)
    asyncio.create_task(woodcraft.run_until_disconnected())

if __name__ == "__main__":
    threading.Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": PORT}).start()
    asyncio.run(main())
