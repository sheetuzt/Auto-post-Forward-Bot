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
def health(): return "Bot is Running Securely!"

def run_web():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
env_admins = os.getenv("DEFAULT_ADMINS", "")
DEFAULT_ADMINS = [int(x.strip()) for x in env_admins.split(",") if x.strip()]

bot = TelegramClient("bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)
userbot = None 
current_owner = None

# States
forwarding = True
skip_next = False
login_state = {}

def is_auth(uid):
    return uid in DEFAULT_ADMINS or uid in get_admins_db()

# --- COMMANDS ---
@bot.on(events.NewMessage(pattern=r"(?i)^/start"))
async def start(e):
    if not is_auth(e.sender_id):
        return await e.reply("❌ Unauthorized Access Denied.")
    
    help_text = """
🚀 **Auto Forwarder Bot (Secure Version)**

🔐 **Auth:** `/login`, `/logout`, `/restart`
📁 **Source:** `/addsource [ID]`, `/remsource [ID]`, `/listsources`
🎯 **Target:** `/addtarget [ID]`, `/removetarget [ID]`, `/listtargets`
⚙️ **Settings:** `/on`, `/off`, `/setdelay [Sec]`, `/skip`, `/resume`
📊 **Stats:** `/status`, `/count`, `/noor`
👤 **Admin:** `/addadmin [ID]`, `/removeadmin [ID]`
    """
    await e.reply(help_text)

# --- LOGIN FLOW ---
@bot.on(events.NewMessage(pattern=r"(?i)^/login"))
async def login(e):
    if not is_auth(e.sender_id): return
    login_state[e.sender_id] = {"step": "phone"}
    await e.reply("📱 Phone Number bheje (+91...)")

@bot.on(events.NewMessage)
async def auth_handler(e):
    if e.sender_id not in login_state or e.text.startswith('/'): return
    state = login_state[e.sender_id]
    global userbot
    if not userbot: 
        userbot = TelegramClient(StringSession(), API_ID, API_HASH)
        await userbot.connect()
    
    try:
        if state["step"] == "phone":
            state["phone"] = e.text.strip()
            await userbot.send_code_request(state["phone"])
            state["step"] = "code"
            await e.reply("✉️ OTP Bhejo (Space dekar: 1 2 3 4 5)")
        elif state["step"] == "code":
            otp = e.text.replace(" ", "")
            try:
                await userbot.sign_in(state["phone"], otp)
                save_session(e.sender_id, userbot.session.save())
                await e.reply("✅ Login Success! Restarting...")
                os.execl(sys.executable, sys.executable, *sys.argv)
            except errors.SessionPasswordNeededError:
                state["step"] = "2fa"; await e.reply("🔐 2FA Password Bheje:")
        elif state["step"] == "2fa":
            await userbot.sign_in(password=e.text.strip())
            save_session(e.sender_id, userbot.session.save())
            await e.reply("✅ Login Success! Restarting...")
            os.execl(sys.executable, sys.executable, *sys.argv)
    except Exception as err:
        await e.reply(f"❌ Error: {err}"); login_state.pop(e.sender_id, None)

@bot.on(events.NewMessage(pattern=r"(?i)^/logout"))
async def logout(e):
    if is_auth(e.sender_id):
        delete_session_db(e.sender_id)
        await e.reply("🛑 Session Clear. Restarting...")
        os.execl(sys.executable, sys.executable, *sys.argv)

# --- MANAGEMENT ---
@bot.on(events.NewMessage(pattern=r"(?i)^/addsource (-?\d+)"))
async def asrc(e):
    if is_auth(e.sender_id):
        add_source_db(e.sender_id, int(e.pattern_match.group(1)))
        await e.reply("✅ Source Added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listsources"))
async def lsrc(e):
    if is_auth(e.sender_id):
        await e.reply(f"📁 Your Sources: `{get_sources(e.sender_id)}`")

@bot.on(events.NewMessage(pattern=r"(?i)^/addtarget (-?\d+)"))
async def atrg(e):
    if is_auth(e.sender_id):
        add_target(e.sender_id, int(e.pattern_match.group(1)))
        await e.reply("✅ Target Added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listtargets"))
async def ltrg(e):
    if is_auth(e.sender_id):
        await e.reply(f"🎯 Your Targets: `{get_targets(e.sender_id)}`")

@bot.on(events.NewMessage(pattern=r"(?i)^/remsource (-?\d+)"))
async def rsrc(e):
    if is_auth(e.sender_id):
        remove_source_db(e.sender_id, int(e.pattern_match.group(1)))
        await e.reply("❌ Source Removed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/removetarget (-?\d+)"))
async def rtrg(e):
    if is_auth(e.sender_id):
        remove_target(e.sender_id, int(e.pattern_match.group(1)))
        await e.reply("❌ Target Removed.")

# --- CONTROL ---
@bot.on(events.NewMessage(pattern=r"(?i)^/on"))
async def on(e):
    if is_auth(e.sender_id):
        global forwarding; forwarding = True; await e.reply("✅ Forwarding ON")

@bot.on(events.NewMessage(pattern=r"(?i)^/off"))
async def off(e):
    if is_auth(e.sender_id):
        global forwarding; forwarding = False; await e.reply("📴 Forwarding OFF")

@bot.on(events.NewMessage(pattern=r"(?i)^/setdelay (\d+)"))
async def sd(e):
    if is_auth(e.sender_id):
        s = int(e.pattern_match.group(1))
        set_delay_db(e.sender_id, s); await e.reply(f"⏱ Delay: {s}s")

@bot.on(events.NewMessage(pattern=r"(?i)^/skip"))
async def sk(e):
    if is_auth(e.sender_id):
        global skip_next; skip_next = True; await e.reply("⏭ Next Skipped")

@bot.on(events.NewMessage(pattern=r"(?i)^/resume"))
async def res(e):
    if is_auth(e.sender_id):
        global skip_next, forwarding; skip_next = False; forwarding = True; await e.reply("▶️ Resumed")

@bot.on(events.NewMessage(pattern=r"(?i)^/count"))
async def cnt(e):
    if is_auth(e.sender_id): await e.reply(f"📊 Forwarded: {get_count(e.sender_id)}")

@bot.on(events.NewMessage(pattern=r"(?i)^/status"))
async def stat(e):
    if is_auth(e.sender_id):
        m = "ON ✅" if forwarding else "OFF ❌"
        await e.reply(f"⚡ Status: {m}\nDelay: {get_delay(e.sender_id)}s")

@bot.on(events.NewMessage(pattern=r"(?i)^/noor"))
async def noor(e):
    if is_auth(e.sender_id):
        msg = f"📊 **Report**\nForwarding: {forwarding}\nTargets: {len(get_targets(e.sender_id))}\nSources: {len(get_sources(e.sender_id))}\nCount: {get_count(e.sender_id)}"
        await e.reply(msg)

@bot.on(events.NewMessage(pattern=r"(?i)^/restart"))
async def rest(e):
    if is_auth(e.sender_id): await e.reply("♻️ Restarting..."); os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on(events.NewMessage(pattern=r"(?i)^/addadmin (\d+)"))
async def aa(e):
    if e.sender_id in DEFAULT_ADMINS:
        uid = int(e.pattern_match.group(1))
        add_admin_db(uid); await e.reply(f"✅ User {uid} added as admin.")

@bot.on(events.NewMessage(pattern=r"(?i)^/removeadmin (\d+)"))
async def ra(e):
    if e.sender_id in DEFAULT_ADMINS:
        uid = int(e.pattern_match.group(1))
        remove_admin_db(uid); await e.reply(f"❌ User {uid} removed.")

# --- ENGINE ---
async def start_services():
    global userbot, current_owner
    sess = get_last_active_session()
    if sess and "owner_id" in sess:
        current_owner = sess["owner_id"]
        try:
            userbot = TelegramClient(StringSession(sess["data"]), API_ID, API_HASH)
            await userbot.start()
            @userbot.on(events.NewMessage)
            async def fw_handler(e):
                global skip_next
                if not forwarding: return
                my_srcs = get_sources(current_owner)
                if e.chat_id not in my_srcs: return
                if skip_next: skip_next = False; return
                
                my_trgs = get_targets(current_owner)
                delay = get_delay(current_owner)
                for t in my_trgs:
                    if not is_forwarded(e.id, t):
                        try:
                            await userbot.send_message(t, e.message)
                            mark_forwarded(e.id, t); inc_count(current_owner)
                            await asyncio.sleep(delay)
                        except: pass
        except Exception as err: print(f"Userbot error: {err}")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.get_event_loop().run_until_complete(start_services())
