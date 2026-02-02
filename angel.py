import os
import sys
import asyncio
import threading
from flask import Flask
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
from angel_db import *

# --- WEB SERVER FOR RENDER ---
app = Flask(__name__)
@app.route('/')
def health(): return "Bot is Active!"

def run_web():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHAT_ID = int(os.getenv("SOURCE_CHAT_ID"))
env_admins = os.getenv("DEFAULT_ADMINS", "7786904376")
DEFAULT_ADMINS = [int(x.strip()) for x in env_admins.split(",") if x.strip()]

bot = TelegramClient("bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)
u_sess = load_session()
userbot = TelegramClient(StringSession(u_sess) if u_sess else StringSession(), API_ID, API_HASH)

forwarding = True
skip_next = False
login_state = {}

def is_admin(uid):
    return uid in DEFAULT_ADMINS or uid in get_admins_db()

# --- START COMMAND ---
@bot.on(events.NewMessage(pattern=r"(?i)^/start"))
async def start(e):
    help_text = """
🌟 **Auto Forward Bot Commands** 🌟

/login - 🔐 Start userbot session
/cancel - ❌ Cancel current process
/status - ⚡️ View bot status
/on - ✅ Launch the bot
/off - 📴 Close the bot
/setdelay [Sec] - ⏱️ Set delay time
/skip - 🛹 Skip next message
/resume - 🏹 Start forwarding
/addtarget [ID] - ✅ Add target chat
/removetarget [ID] - 😡 Remove target
/listtargets - 🆔 View all targets
/count - 📊 Total forwarded files
/noor - 👀 Detailed status report
/addadmin [ID] - 👤 Add new admin
/restart - ♻️ Restart the bot safely
    """
    await e.reply(help_text)

# --- CANCEL COMMAND ---
@bot.on(events.NewMessage(pattern=r"(?i)^/cancel"))
async def cancel(e):
    if e.sender_id in login_state:
        login_state.pop(e.sender_id)
        await e.reply("❌ Current process (Login) has been cancelled.")
    else:
        await e.reply("No active process to cancel.")

# --- LOGIN FLOW (WITH 2FA SUPPORT) ---
@bot.on(events.NewMessage(pattern=r"(?i)^/login"))
async def login(e):
    if not is_admin(e.sender_id): return
    login_state[e.sender_id] = {"step": "phone"}
    await e.reply("📱 Please send your phone number (+91...) or use /cancel to stop.")

@bot.on(events.NewMessage)
async def login_handler(e):
    if e.sender_id not in login_state or e.text.startswith('/'): return
    state = login_state[e.sender_id]
    
    try:
        if state["step"] == "phone":
            state["phone"] = e.text.strip()
            await userbot.connect()
            await userbot.send_code_request(state["phone"])
            state["step"] = "code"
            await e.reply("✉️ OTP bhejo (jaise: 1 2 3 4 5)")
        
        elif state["step"] == "code":
            otp = e.text.replace(" ", "")
            try:
                await userbot.sign_in(state["phone"], otp)
                # If success without 2FA
                save_session(userbot.session.save())
                login_state.pop(e.sender_id)
                await e.reply("✅ Login Successful! Restarting...")
                os.execl(sys.executable, sys.executable, *sys.argv)
            except errors.SessionPasswordNeededError:
                state["step"] = "password"
                await e.reply("🔐 **Two-Step Verification detected!**\nAb apna 2FA Password bhejo.")
        
        elif state["step"] == "password":
            password = e.text.strip()
            await userbot.sign_in(password=password)
            save_session(userbot.session.save())
            login_state.pop(e.sender_id)
            await e.reply("✅ Login Successful (with 2FA)! Restarting...")
            os.execl(sys.executable, sys.executable, *sys.argv)

    except Exception as err:
        await e.reply(f"❌ Error occurred: {str(err)}\nProcess cancelled.")
        login_state.pop(e.sender_id, None)

# --- CORE COMMANDS (ADMIN ONLY) ---
@bot.on(events.NewMessage(pattern=r"(?i)^/status"))
async def status(e):
    mode = "Active ✅" if forwarding else "Inactive ❌"
    await e.reply(f"⚡️ Status: {mode}\nDelay: {get_delay()}s\nTargets: {len(get_targets())}")

@bot.on(events.NewMessage(pattern=r"(?i)^/on"))
async def on_cmd(e):
    if not is_admin(e.sender_id): return
    global forwarding
    forwarding = True
    await e.reply("✅ Forwarding ON")

@bot.on(events.NewMessage(pattern=r"(?i)^/off"))
async def off_cmd(e):
    if not is_admin(e.sender_id): return
    global forwarding
    forwarding = False
    await e.reply("📴 Forwarding OFF")

@bot.on(events.NewMessage(pattern=r"(?i)^/addtarget (-?\d+)"))
async def addtarget(e):
    if not is_admin(e.sender_id): return
    tid = int(e.pattern_match.group(1))
    add_target(tid)
    await e.reply(f"✅ Target {tid} added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/count"))
async def count_cmd(e):
    await e.reply(f"📊 Total Forwarded Files: {get_count()}")

@bot.on(events.NewMessage(pattern=r"(?i)^/restart"))
async def restart_cmd(e):
    if not is_admin(e.sender_id): return
    await e.reply("♻️ Restarting...")
    os.execl(sys.executable, sys.executable, *sys.argv)

# --- FORWARDING ENGINE ---
@userbot.on(events.NewMessage(chats=SOURCE_CHAT_ID))
async def forwarder(e):
    global skip_next
    if not forwarding or skip_next:
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
            except Exception as err: print(f"Error: {err}")

# --- START ---
async def main():
    if u_sess: await userbot.start()
    print("Bot is ready.")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.get_event_loop().run_until_complete(main())
