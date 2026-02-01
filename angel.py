import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from angel_db import *

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHAT_ID = int(os.getenv("SOURCE_CHAT_ID"))

# ================= CLIENTS =================
bot = TelegramClient("bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

user_session = load_session()
userbot = TelegramClient(StringSession(user_session) if user_session else StringSession(), API_ID, API_HASH)

forwarding = True
delay_seconds = 5
skip_next = False
login_state = {}

# ================= LOGIN =================
@bot.on(events.NewMessage(pattern="/login"))
async def login(e):
    login_state[e.sender_id] = {"step": "phone"}
    await e.reply("📱 Send phone number with country code")

@bot.on(events.NewMessage)
async def login_flow(e):
    if e.sender_id not in login_state:
        return

    state = login_state[e.sender_id]

    if state["step"] == "phone":
        state["phone"] = e.text.strip()
        await userbot.connect()
        await userbot.send_code_request(state["phone"])
        state["step"] = "code"
        await e.reply("✉️ OTP bhejo")

    elif state["step"] == "code":
        await userbot.sign_in(state["phone"], e.text.strip())
        session_str = userbot.session.save()
        save_session(session_str)
        login_state.pop(e.sender_id)
        await e.reply("✅ Login successful")

# ================= FORWARD =================
async def forward_message(msg):
    global skip_next

    if skip_next:
        skip_next = False
        return

    targets = get_targets()
    for t in targets:
        if not is_forwarded(msg.id, t):
            if msg.media:
                await userbot.send_file(t, msg.media, caption=msg.text)
            else:
                await userbot.send_message(t, msg.text)
            mark_forwarded(msg.id, t)
            await asyncio.sleep(delay_seconds)

@userbot.on(events.NewMessage(chats=SOURCE_CHAT_ID))
async def handler(e):
    if forwarding:
        await forward_message(e.message)

# ================= COMMANDS =================
@bot.on(events.NewMessage(pattern="/start"))
async def start(e):
    await e.reply("🤖 Angel Forward Bot Ready")

@bot.on(events.NewMessage(pattern="/on"))
async def on_cmd(e):
    global forwarding
    forwarding = True
    await e.reply("✅ Forwarding ON")

@bot.on(events.NewMessage(pattern="/off"))
async def off_cmd(e):
    global forwarding
    forwarding = False
    await e.reply("❌ Forwarding OFF")

@bot.on(events.NewMessage(pattern="/status"))
async def status(e):
    await e.reply(f"Forwarding: {forwarding}\nDelay: {delay_seconds}s")

@bot.on(events.NewMessage(pattern=r"/setdelay (\d+)"))
async def setdelay(e):
    global delay_seconds
    delay_seconds = int(e.pattern_match.group(1))
    await e.reply(f"⏱ Delay set to {delay_seconds}")

@bot.on(events.NewMessage(pattern=r"/addtarget (-?\d+)"))
async def addtarget(e):
    add_target(int(e.pattern_match.group(1)))
    await e.reply("✅ Target added")

@bot.on(events.NewMessage(pattern=r"/removetarget (-?\d+)"))
async def removetarget(e):
    remove_target(int(e.pattern_match.group(1)))
    await e.reply("❌ Target removed")

@bot.on(events.NewMessage(pattern="/listtargets"))
async def listtargets(e):
    await e.reply(str(get_targets()))

@bot.on(events.NewMessage(pattern="/skip"))
async def skip(e):
    global skip_next
    skip_next = True
    await e.reply("⏭ Skipping next")

@bot.on(events.NewMessage(pattern="/resume"))
async def resume(e):
    global forwarding
    forwarding = True
    await e.reply("▶️ Resumed")

@bot.on(events.NewMessage(pattern="/count"))
async def count(e):
    await e.reply(f"📊 {get_count()} forwarded")

@bot.on(events.NewMessage(pattern="/noor"))
async def noor(e):
    txt = f"""
📊 Detailed Report
Forwarding: {forwarding}
Targets: {len(get_targets())}
Total Forwarded: {get_count()}
Delay: {delay_seconds}s
"""
    await e.reply(txt)

@bot.on(events.NewMessage(pattern="/restart"))
async def restart(e):
    await e.reply("♻️ Restarting")
    os._exit(0)

# ================= MAIN =================
async def main():
    await userbot.start()
    print("Userbot started")
    await bot.run_until_disconnected()

asyncio.run(main())
