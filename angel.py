import os
import sys
import asyncio
import threading
from flask import Flask
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
from angel_db import *

# --- WEB SERVER (For Render) ---
app = Flask(__name__)
@app.route('/')
def health(): return "Bot is Alive & Running!"

def run_web():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Admins list processing
env_admins = os.getenv("DEFAULT_ADMINS", "")
AUTHORIZED_USERS = [int(x.strip()) for x in env_admins.split(",") if x.strip()]

# Clients
bot = TelegramClient("bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)
userbot = None # Will be initialized dynamically
current_user_id = None # Tracks whose session is running

# Global Runtime States
forwarding = True
skip_next = False
login_state = {}

# --- SECURITY ---
def is_authorized(uid):
    return uid in AUTHORIZED_USERS or uid in get_admins_db()

# --- START & HELP ---
@bot.on(events.NewMessage(pattern=r"(?i)^/start"))
async def start(e):
    if not is_authorized(e.sender_id):
        await e.reply("🚫 **Access Denied.** You are not authorized.")
        return
    
    msg = """
🤖 **Auto Forward Bot - Full Control**
*Current Session: "User Specific"*

🔐 **Account:**
`/login` - Login Userbot
`/logout` - Logout & Reset
`/status` - Check Status

⚙️ **Setup (Private Data):**
`/addsource [ID]` - Add Source
`/remsource [ID]` - Remove Source
`/listsources` - View Sources
`/addtarget [ID]` - Add Target
`/removetarget [ID]` - Remove Target
`/listtargets` - View Targets

🎮 **Controls:**
`/on` - Turn ON Forwarding
`/off` - Turn OFF Forwarding
`/setdelay [Sec]` - Set Delay (e.g., 10)
`/skip` - Skip Next Message
`/resume` - Resume Forwarding
`/count` - View Stats
`/noor` - Detailed Report
`/restart` - Restart Bot
    """
    await e.reply(msg)

# --- LOGIN FLOW (Supports 2FA) ---
@bot.on(events.NewMessage(pattern=r"(?i)^/login"))
async def login_cmd(e):
    if not is_authorized(e.sender_id): return
    login_state[e.sender_id] = {"step": "phone"}
    await e.reply("📱 Phone number bhejo (+91...)")

@bot.on(events.NewMessage)
async def login_handler(e):
    if e.sender_id not in login_state or e.text.startswith('/'): return
    
    state = login_state[e.sender_id]
    global userbot, current_user_id
    
    # Init temp client for login
    if not userbot: 
        userbot = TelegramClient(StringSession(), API_ID, API_HASH)
        await userbot.connect()

    try:
        if state["step"] == "phone":
            state["phone"] = e.text.strip()
            await userbot.send_code_request(state["phone"])
            state["step"] = "code"
            await e.reply("✉️ OTP Bhejo (spaces ke saath: 1 2 3 4 5)")
        
        elif state["step"] == "code":
            otp = e.text.replace(" ", "")
            try:
                await userbot.sign_in(state["phone"], otp)
                save_session(e.sender_id, userbot.session.save())
                login_state.pop(e.sender_id)
                await e.reply("✅ Login Successful! Restarting Bot...")
                os.execl(sys.executable, sys.executable, *sys.argv)
            except errors.SessionPasswordNeededError:
                state["step"] = "password"
                await e.reply("🔐 2FA Password Bhejo:")
        
        elif state["step"] == "password":
            await userbot.sign_in(password=e.text.strip())
            save_session(e.sender_id, userbot.session.save())
            login_state.pop(e.sender_id)
            await e.reply("✅ Login Successful (2FA)! Restarting Bot...")
            os.execl(sys.executable, sys.executable, *sys.argv)
            
    except Exception as err:
        await e.reply(f"❌ Error: {err}")
        login_state.pop(e.sender_id, None)

@bot.on(events.NewMessage(pattern=r"(?i)^/logout"))
async def logout(e):
    if not is_authorized(e.sender_id): return
    delete_session_db(e.sender_id)
    await e.reply("🛑 Session deleted. Logged out.")
    os.execl(sys.executable, sys.executable, *sys.argv)

# --- SOURCE & TARGET MANAGEMENT ---
@bot.on(events.NewMessage(pattern=r"(?i)^/addsource (-?\d+)"))
async def add_src(e):
    if not is_authorized(e.sender_id): return
    add_source_db(e.sender_id, int(e.pattern_match.group(1)))
    await e.reply("✅ Source Added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/remsource (-?\d+)"))
async def rem_src(e):
    if not is_authorized(e.sender_id): return
    remove_source_db(e.sender_id, int(e.pattern_match.group(1)))
    await e.reply("❌ Source Removed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listsources"))
async def list_src(e):
    if not is_authorized(e.sender_id): return
    await e.reply(f"📂 **Your Sources:** `{get_sources(e.sender_id)}`")

@bot.on(events.NewMessage(pattern=r"(?i)^/addtarget (-?\d+)"))
async def add_trg(e):
    if not is_authorized(e.sender_id): return
    add_target(e.sender_id, int(e.pattern_match.group(1)))
    await e.reply("✅ Target Added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/removetarget (-?\d+)"))
async def rem_trg(e):
    if not is_authorized(e.sender_id): return
    remove_target(e.sender_id, int(e.pattern_match.group(1)))
    await e.reply("❌ Target Removed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listtargets"))
async def list_trg(e):
    if not is_authorized(e.sender_id): return
    await e.reply(f"🎯 **Your Targets:** `{get_targets(e.sender_id)}`")

# --- CONTROL COMMANDS (Restored) ---
@bot.on(events.NewMessage(pattern=r"(?i)^/on"))
async def on_cmd(e):
    if not is_authorized(e.sender_id): return
    global forwarding
    forwarding = True
    await e.reply("✅ Forwarding **ENABLED**.")

@bot.on(events.NewMessage(pattern=r"(?i)^/off"))
async def off_cmd(e):
    if not is_authorized(e.sender_id): return
    global forwarding
    forwarding = False
    await e.reply("📴 Forwarding **DISABLED**.")

@bot.on(events.NewMessage(pattern=r"(?i)^/skip"))
async def skip_cmd(e):
    if not is_authorized(e.sender_id): return
    global skip_next
    skip_next = True
    await e.reply("⏭️ Next message will be **SKIPPED**.")

@bot.on(events.NewMessage(pattern=r"(?i)^/resume"))
async def resume_cmd(e):
    if not is_authorized(e.sender_id): return
    global skip_next, forwarding
    skip_next = False
    forwarding = True
    await e.reply("▶️ Resumed normal operation.")

@bot.on(events.NewMessage(pattern=r"(?i)^/setdelay (\d+)"))
async def setdelay_cmd(e):
    if not is_authorized(e.sender_id): return
    sec = int(e.pattern_match.group(1))
    set_delay_db(e.sender_id, sec)
    await e.reply(f"⏱️ Delay set to **{sec} seconds** for your session.")

@bot.on(events.NewMessage(pattern=r"(?i)^/count"))
async def count_cmd(e):
    if not is_authorized(e.sender_id): return
    c = get_count(e.sender_id)
    await e.reply(f"📊 **Total Forwarded:** {c}")

@bot.on(events.NewMessage(pattern=r"(?i)^/restart"))
async def restart_cmd(e):
    if not is_authorized(e.sender_id): return
    await e.reply("♻️ Restarting System...")
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on(events.NewMessage(pattern=r"(?i)^/status"))
async def status_cmd(e):
    if not is_authorized(e.sender_id): return
    mode = "ON ✅" if forwarding else "OFF ❌"
    d = get_delay(e.sender_id)
    await e.reply(f"⚡ **Status:** {mode}\n⏱ **Delay:** {d}s\n👤 **Active User:** {current_user_id}")

@bot.on(events.NewMessage(pattern=r"(?i)^/noor"))
async def noor_cmd(e):
    if not is_authorized(e.sender_id): return
    msg = f"""
🕵️ **Detailed Report**
------------------------
Active: {forwarding}
Sources: {len(get_sources(e.sender_id))}
Targets: {len(get_targets(e.sender_id))}
Total Count: {get_count(e.sender_id)}
Delay: {get_delay(e.sender_id)}s
    """
    await e.reply(msg)

# --- CORE LOGIC ---
async def start_bot():
    global userbot, current_user_id
    
    # 1. Load Last Active Session
    # Note: Render pe simple rakhne ke liye hum last login session uthayenge
    session_data = get_last_active_session()
    
    if session_data:
        current_user_id = session_data["owner_id"]
        print(f"🔄 Loading Session for User: {current_user_id}")
        userbot = TelegramClient(StringSession(session_data["data"]), API_ID, API_HASH)
        await userbot.start()
        
        # 2. Register Forwarder
        @userbot.on(events.NewMessage)
        async def forwarder(e):
            global skip_next
            # Only process if ON
            if not forwarding: return
            
            # Check if message is from valid source for this user
            my_sources = get_sources(current_user_id)
            if e.chat_id not in my_sources: return

            # Skip Logic
            if skip_next:
                print("Skipped message as per command.")
                skip_next = False
                return

            my_targets = get_targets(current_user_id)
            delay = get_delay(current_user_id)
            
            for t in my_targets:
                if not is_forwarded(e.id, t):
                    try:
                        await userbot.send_message(t, e.message)
                        mark_forwarded(e.id, t)
                        inc_count(current_user_id)
                        print(f"Forwarded msg {e.id} to {t}")
                        await asyncio.sleep(delay)
                    except Exception as err:
                        print(f"Forward Error: {err}")
    else:
        print("⚠️ No session found. Please /login via Bot.")

    print("🤖 Bot System Ready.")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.get_event_loop().run_until_complete(start_bot())
