# angel.py

import os
import asyncio
import threading
from flask import Flask
from dotenv import load_dotenv

from telethon import TelegramClient, events
from telethon.sessions import StringSession

from settings import (
    setup_extra_handlers,
    load_initial_settings,
    is_admin,
    get_all_target_channels,
    add_target_channel,
    remove_target_channel
)

from angel_db import (
    is_forwarded_for_target,
    mark_as_forwarded_for_target,
    collection
)

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHAT_ID = int(os.getenv("SOURCE_CHAT_ID"))
STATUS_URL = os.getenv("STATUS_URL")
PORT = int(os.getenv("PORT", 8080))

app = Flask(__name__)

# ================= Clients =================
bot = TelegramClient("bot", API_ID, API_HASH)
woodcraft = TelegramClient("userbot", API_ID, API_HASH)

forwarding_enabled = True
woodcraft.delay_seconds = 5
woodcraft.skip_next_message = False


# ================= Forward Logic =================
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
    elif woodcraft.skip_next_message:
        woodcraft.skip_next_message = False


# ================= LOGIN SYSTEM =================
login_state = {}


@bot.on(events.NewMessage(pattern=r'^/login$'))
async def login_start(event):
    login_state[event.sender_id] = {}
    await event.reply("📱 Send your phone number with country code.\nExample: +919876543210")


@bot.on(events.NewMessage)
async def login_flow(event):
    if event.sender_id not in login_state:
        return

    state = login_state[event.sender_id]

    if "phone" not in state:
        state["phone"] = event.text.strip()
        await woodcraft.send_code_request(state["phone"])
        await event.reply("🔑 OTP sent. Send OTP now.")
        return

    if "otp" not in state:
        state["otp"] = event.text.strip()
        try:
            await woodcraft.sign_in(state["phone"], state["otp"])
            await event.reply("✅ Login successful! Restarting...")
            login_state.pop(event.sender_id)
            os._exit(0)
        except Exception as e:
            await event.reply(f"❌ Error: {e}")


# ================= Commands =================
@bot.on(events.NewMessage(pattern=r'^/status$'))
async def status(event):
    if not is_admin(event.sender_id):
        return
    total = collection.count_documents({})
    await bot.send_file(
        event.chat_id,
        file=STATUS_URL,
        caption=f"📊 Total Forwarded: `{total}`",
    )


# ================= Flask =================
@app.route("/")
def home():
    return "Bot running", 200


# ================= Main =================
async def main():
    await bot.start(bot_token=BOT_TOKEN)
    await woodcraft.connect()

    if await woodcraft.is_user_authorized():
        print("✅ User logged in")

        await load_initial_settings(woodcraft)
        setup_extra_handlers(bot)

        await asyncio.gather(
            bot.run_until_disconnected(),
            woodcraft.run_until_disconnected()
        )
    else:
        print("⚠️ Waiting for /login from bot...")
        setup_extra_handlers(bot)
        await bot.run_until_disconnected()


if __name__ == "__main__":
    threading.Thread(
        target=app.run,
        kwargs={"host": "0.0.0.0", "port": PORT},
    ).start()

    asyncio.run(main())
