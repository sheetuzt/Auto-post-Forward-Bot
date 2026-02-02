import os
import sys
import asyncio
import threading
from flask import Flask
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
from angel_db import *

app = Flask(__name__)
@app.route('/')
def health(): return "Bot is Alive!"

def run_web():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEFAULT_ADMINS = [int(x.strip()) for x in os.getenv("DEFAULT_ADMINS", "").split(",") if x.strip()]

bot = TelegramClient("bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)
u_sess = load_session()
userbot = TelegramClient(StringSession(u_sess) if u_sess else StringSession(), API_ID, API_HASH)

forwarding = True
skip_next = False
login_state = {}

def is_admin(uid):
    return uid in DEFAULT_ADMINS or uid in get_admins_db()

# --- START ---
@bot.on(events.NewMessage(pattern=r"(?i)^/start"))
async def start(e):
    help_msg = """
🤖 **Forwarder Bot Commands** 🤖

**Login/Logout:**
/login - Start Session
/logout - Remove account & session
/cancel - Stop current process

**Source/Target Management:**
/addsource [ID] - Add source chat
/remsource [ID] - Remove source chat
/listsources - View sources
/addtarget [ID] - Add target chat
/removetarget [ID] - Remove target chat
/listtargets - View targets

**Controls:**
/on - Forwarding ON
/off - Forwarding OFF
/resume - Resume if stopped
/setdelay [Sec] - Set delay
/skip - Skip next message
/status - View bot status
/noor - Detailed Report
/restart - Reboot bot
    """
    await e.reply(help_msg)

# --- LOGIN & LOGOUT ---
@bot.on(events.NewMessage(pattern=r"(?i)^/logout"))
async def logout(e):
    if not is_admin(e.sender_id): return
    delete_session_db()
    await e.reply("✅ Session deleted and logged out. Restarting...")
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on(events.NewMessage(pattern=r"(?i)^/login"))
async def login(e):
    if not is_admin(e.sender_id): return
    login_state[e.sender_id] = {"step": "phone"}
    await e.reply("📱 Phone number bhejo (+91...)")

@bot.on(events.NewMessage)
async def login_flow(e):
    if e.sender_id not in login_state or e.text.startswith('/'): return
    state = login_state[e.sender_id]
    try:
        if state["step"] == "phone":
            state["phone"] = e.text.strip()
            await userbot.connect()
            await userbot.send_code_request(state["phone"])
            state["step"] = "code"
            await e.reply("✉️ OTP bhejo (Space ke sath, jaise 1 2 3 4 5)")
        elif state["step"] == "code":
            otp = e.text.replace(" ", "")
            try:
                await userbot.sign_in(state["phone"], otp)
                save_session(userbot.session.save())
                login_state.pop(e.sender_id)
                await e.reply("✅ Login Success! Restarting...")
                os.execl(sys.executable, sys.executable, *sys.argv)
            except errors.SessionPasswordNeededError:
                state["step"] = "password"
                await e.reply("🔐 2FA Password bhejo:")
        elif state["step"] == "password":
            await userbot.sign_in(password=e.text.strip())
            save_session(userbot.session.save())
            login_state.pop(e.sender_id)
            await e.reply("✅ Login Success (2FA)! Restarting...")
            os.execl(sys.executable, sys.executable, *sys.argv)
    except Exception as err:
        await e.reply(f"❌ Error: {err}")
        login_state.pop(e.sender_id, None)

# --- COMMANDS (FIXED PATTERNS) ---
@bot.on(events.NewMessage(pattern=r"(?i)^/status"))
async def status(e):
    mode = "Active ✅" if forwarding else "Inactive ❌"
    await e.reply(f"⚡ Status: {mode}\nSources: {len(get_sources())}\nTargets: {len(get_targets())}")

@bot.on(events.NewMessage(pattern=r"(?i)^/noor"))
async def noor(e):
    txt = f"📊 **Report**\nForwarding: {forwarding}\nSources: {get_sources()}\nTargets: {get_targets()}\nCount: {get_count()}\nDelay: {get_delay()}s"
    await e.reply(txt)

@bot.on(events.NewMessage(pattern=r"(?i)^/setdelay (\d+)"))
async def setdelay(e):
    if not is_admin(e.sender_id): return
    sec = int(e.pattern_match.group(1))
    set_delay_db(sec)
    await e.reply(f"⏱ Delay set to {sec}s")

@bot.on(events.NewMessage(pattern=r"(?i)^/addsource (-?\d+)"))
async def add_src(e):
    if not is_admin(e.sender_id): return
    sid = int(e.pattern_match.group(1))
    add_source_db(sid)
    await e.reply(f"✅ Source {sid} added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/remsource (-?\d+)"))
async def rem_src(e):
    if not is_admin(e.sender_id): return
    sid = int(e.pattern_match.group(1))
    remove_source_db(sid)
    await e.reply(f"❌ Source {sid} removed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listsources"))
async def list_src(e):
    await e.reply(f"📁 Sources: {get_sources()}")

@bot.on(events.NewMessage(pattern=r"(?i)^/addtarget (-?\d+)"))
async def add_trg(e):
    if not is_admin(e.sender_id): return
    tid = int(e.pattern_match.group(1))
    add_target(tid)
    await e.reply(f"✅ Target {tid} added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/removetarget (-?\d+)"))
async def rem_trg(e):
    if not is_admin(e.sender_id): return
    tid = int(e.pattern_match.group(1))
    remove_target(tid)
    await e.reply(f"❌ Target {tid} removed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listtargets"))
async def list_trg(e):
    await e.reply(f"🎯 Targets: {get_targets()}")

@bot.on(events.NewMessage(pattern=r"(?i)^/resume"))
async def resume(e):
    global forwarding
    forwarding = True
    await e.reply("▶️ Resumed")

@bot.on(events.NewMessage(pattern=r"(?i)^/on"))
async def on_cmd(e):
    global forwarding
    forwarding = True
    await e.reply("✅ Forwarding ON")

@bot.on(events.NewMessage(pattern=r"(?i)^/off"))
async def off_cmd(e):
    global forwarding
    forwarding = False
    await e.reply("📴 Forwarding OFF")

@bot.on(events.NewMessage(pattern=r"(?i)^/cancel"))
async def cancel(e):
    login_state.pop(e.sender_id, None)
    await e.reply("❌ Process Cancelled")

# --- FORWARDER LOGIC ---
@userbot.on(events.NewMessage)
async def main_forwarder(e):
    global skip_next
    sources = get_sources()
    if not forwarding or e.chat_id not in sources: return
    
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
            except Exception as err: print(f"Error: {err}")

# --- START ---
async def start_bot():
    if u_sess: await userbot.start()
    print("Bot is ready!")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.get_event_loop().run_until_complete(start_bot())
