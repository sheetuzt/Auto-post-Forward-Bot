import os
import asyncio
import threading
from flask import Flask
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

from settings import setup_extra_handlers, load_initial_settings, is_admin
from settings import get_all_target_channels, add_target_channel, remove_target_channel
from angel_db import is_forwarded_for_target, mark_as_forwarded_for_target
from angel_db import collection, settings_col

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
STATUS_URL = os.getenv("STATUS_URL")
SOURCE_CHAT_ID = int(os.getenv("SOURCE_CHAT_ID").strip().replace("\u200e",""))
PORT = int(os.getenv("PORT", 8080))

# 🤖 Bot Client
bot = TelegramClient("bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# 👤 User Client (Mongo session)
session_data = settings_col.find_one({"key": "session"})
if session_data:
    woodcraft = TelegramClient(StringSession(session_data["value"]), API_ID, API_HASH)
else:
    woodcraft = TelegramClient(StringSession(), API_ID, API_HASH)

woodcraft.delay_seconds = 5
woodcraft.skip_next_message = False
forwarding_enabled = True
app = Flask(__name__)

# ================= LOGIN VIA BOT =================
login_state = {}

@bot.on(events.NewMessage(pattern="/login"))
async def login_start(event):
    login_state[event.sender_id] = {"step": "phone"}
    await event.reply("📱 Send phone number with country code")

@bot.on(events.NewMessage)
async def login_flow(event):
    uid = event.sender_id
    if uid not in login_state:
        return

    state = login_state[uid]

    if state["step"] == "phone":
        phone = event.text.strip()
        state["phone"] = phone
        await woodcraft.connect()
        await woodcraft.send_code_request(phone)
        state["step"] = "otp"
        await event.reply("🔐 Send OTP")

    elif state["step"] == "otp":
        otp = event.text.strip()
        await woodcraft.sign_in(state["phone"], otp)

        session_str = woodcraft.session.save()
        settings_col.update_one(
            {"key": "session"},
            {"$set": {"value": session_str}},
            upsert=True
        )

        await event.reply("✅ Login successful! Session saved.")
        del login_state[uid]

# ================= FORWARD =================
async def send_without_tag(original_msg):
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

@woodcraft.on(events.NewMessage(chats=SOURCE_CHAT_ID))
async def new_message_handler(event):
    if forwarding_enabled and not woodcraft.skip_next_message:
        await asyncio.sleep(woodcraft.delay_seconds)
        await send_without_tag(event.message)

# ================= BOT COMMANDS (original) =================
@bot.on(events.NewMessage(pattern=r'^/on$'))
async def on_handler(event):
    global forwarding_enabled
    forwarding_enabled = True
    await event.reply("✅ Forwarding ON")

@bot.on(events.NewMessage(pattern=r'^/off$'))
async def off_handler(event):
    global forwarding_enabled
    forwarding_enabled = False
    await event.reply("❌ Forwarding OFF")

@bot.on(events.NewMessage(pattern=r'^/addtarget\s+(-?\d+)$'))
async def addtarget_handler(event):
    chat_id = int(event.pattern_match.group(1))
    await add_target_channel(chat_id)
    await event.reply(f"✅ Target added `{chat_id}`")

@bot.on(events.NewMessage(pattern=r'^/removetarget\s+(-?\d+)$'))
async def removetarget_handler(event):
    chat_id = int(event.pattern_match.group(1))
    await remove_target_channel(chat_id)
    await event.reply(f"❌ Target removed `{chat_id}`")

@bot.on(events.NewMessage(pattern=r'^/listtargets$'))
async def list_targets_handler(event):
    targets = await get_all_target_channels()
    msg = "\n".join(f"`{t}`" for t in targets) if targets else "No targets"
    await event.reply(msg)

@bot.on(events.NewMessage(pattern=r'^/count$'))
async def count_handler(event):
    total = collection.count_documents({})
    await event.reply(f"📊 Total Forwarded: `{total}`", parse_mode='md')

# settings.py ke commands bot pe attach
# ================= WEB =================
@app.route("/")
def home():
    return "Angel Bot Running", 200

# ================= MAIN =================
async def main():
    await woodcraft.connect()

    if await woodcraft.is_user_authorized():
        print("✅ User session loaded")
    else:
        print("⚠️ Login required via bot /login")

    await load_initial_settings(woodcraft)
    setup_extra_handlers(bot)

    await asyncio.gather(
        woodcraft.run_until_disconnected(),
        bot.run_until_disconnected()
    )

if __name__ == "__main__":
    threading.Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": PORT}).start()
    asyncio.run(main())
