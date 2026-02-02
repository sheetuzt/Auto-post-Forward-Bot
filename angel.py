import os
import sys
import asyncio
import threading
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from angel_db import *

# --- RENDER/HEROKU PORT FIX ---
app = Flask(__name__)
@app.route('/')
def health(): return "Bot is Alive!"

def run_web():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHAT_ID = int(os.getenv("SOURCE_CHAT_ID"))
DEFAULT_ADMINS = [int(x) for x in os.getenv("DEFAULT_ADMINS", "").split(",") if x.strip()]

# Clients
bot = TelegramClient("bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)
u_sess = load_session()
userbot = TelegramClient(StringSession(u_sess) if u_sess else StringSession(), API_ID, API_HASH)

# Global States
forwarding = True
skip_next = False
login_state = {}

def is_admin(uid):
    return uid in DEFAULT_ADMINS or uid in get_admins_db()

# --- LOGIN FLOW ---
@bot.on(events.NewMessage(pattern="/login"))
async def login(e):
    if not is_admin(e.sender_id): return
    login_state[e.sender_id] = {"step": "phone"}
    await e.reply("📱 Please send your phone number with country code (e.g. +91...)")

@bot.on(events.NewMessage)
async def login_handler(e):
    if e.sender_id not in login_state: return
    state = login_state[e.sender_id]
    
    if state["step"] == "phone":
        state["phone"] = e.text.strip()
        await userbot.connect()
        await userbot.send_code_request(state["phone"])
        state["step"] = "code"
        await e.reply("✉️ OTP bhejo (jaise: 1 2 3 4 5)")
    
    elif state["step"] == "code":
        try:
            otp = e.text.replace(" ", "")
            await userbot.sign_in(state["phone"], otp)
            save_session(userbot.session.save())
            login_state.pop(e.sender_id)
            await e.reply("✅ Login Successful! Bot restarting...")
            os.execl(sys.executable, sys.executable, *sys.argv)
        except Exception as err:
            await e.reply(f"❌ Error: {str(err)}")

# --- COMMANDS ---
@bot.on(events.NewMessage(pattern="/status"))
async def status(e):
    mode = "Active ✅" if forwarding else "Inactive ❌"
    await e.reply(f"⚡️ Bot Status: {mode}\nDelay: {get_delay()}s\nTargets: {len(get_targets())}")

@bot.on(events.NewMessage(pattern=r"/setdelay (\d+)"))
async def setdelay(e):
    if not is_admin(e.sender_id): return
    sec = int(e.pattern_match.group(1))
    set_delay_db(sec)
    await e.reply(f"⏱️ Delay set to {sec} seconds.")

@bot.on(events.NewMessage(pattern=r"/addtarget (-?\d+)"))
async def addtarget(e):
    if not is_admin(e.sender_id): return
    tid = int(e.pattern_match.group(1))
    add_target(tid)
    await e.reply(f"✅ Target {tid} added.")

@bot.on(events.NewMessage(pattern=r"/removetarget (-?\d+)"))
async def remtarget(e):
    if not is_admin(e.sender_id): return
    tid = int(e.pattern_match.group(1))
    remove_target(tid)
    await e.reply(f"😡 Target {tid} removed.")

@bot.on(events.NewMessage(pattern="/listtargets"))
async def listt(e):
    t = get_targets()
    await e.reply(f"🆔 Target IDs: {t}")

@bot.on(events.NewMessage(pattern="/on"))
async def on_cmd(e):
    global forwarding
    forwarding = True
    await e.reply("✅ Bot Launched / Forwarding Started")

@bot.on(events.NewMessage(pattern="/off"))
async def off_cmd(e):
    global forwarding
    forwarding = False
    await e.reply("📴 Bot Closed / Forwarding Stopped")

@bot.on(events.NewMessage(pattern="/skip"))
async def skip_cmd(e):
    global skip_next
    skip_next = True
    await e.reply("🛹 Next message will be skipped.")

@bot.on(events.NewMessage(pattern="/resume"))
async def resume_cmd(e):
    global forwarding
    forwarding = True
    await e.reply("🏹 Forwarding Resumed.")

@bot.on(events.NewMessage(pattern="/count"))
async def count_cmd(e):
    await e.reply(f"📊 Total Forwarded Files: {get_count()}")

@bot.on(events.NewMessage(pattern="/noor"))
async def noor_cmd(e):
    msg = f"""
👀 **Detailed Report**
- Forwarding: {'ON' if forwarding else 'OFF'}
- Total Targets: {len(get_targets())}
- Total Forwarded: {get_count()}
- Current Delay: {get_delay()}s
    """
    await e.reply(msg)

@bot.on(events.NewMessage(pattern="/restart"))
async def restart_cmd(e):
    if not is_admin(e.sender_id): return
    await e.reply("♻️ Restarting bot safely...")
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on(events.NewMessage(pattern=r"/addadmin (\d+)"))
async def addadmin(e):
    if e.sender_id not in DEFAULT_ADMINS: return
    uid = int(e.pattern_match.group(1))
    add_admin_db(uid)
    await e.reply(f"✅ User {uid} added as admin.")

# --- FORWARDING CORE ---
@userbot.on(events.NewMessage(chats=SOURCE_CHAT_ID))
async def forwarder(e):
    global skip_next
    if not forwarding: return
    if skip_next:
        skip_next = False
        return
    
    targets = get_targets()
    delay = get_delay()
    
    for t in targets:
        if not is_forwarded(e.id, t):
            try:
                await userbot.send_message(t, e.message)
                mark_forwarded(e.id, t)
                inc_count()
                await asyncio.sleep(delay)
            except Exception as err:
                print(f"Error forwarding: {err}")

# --- MAIN ---
async def start_services():
    if u_sess:
        await userbot.start()
    print("Bot is running...")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_services())
