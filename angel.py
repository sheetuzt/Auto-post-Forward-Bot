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
# Aapka ID .env mein DEFAULT_ADMINS mein hona chahiye
DEFAULT_ADMINS = [int(x.strip()) for x in os.getenv("DEFAULT_ADMINS", "").split(",") if x.strip()]

bot = TelegramClient("bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

user_clients = {} 
login_state = {}
skip_next_msg = {}

# --- AUTH LOGIC ---
def is_owner(uid):
    return uid in DEFAULT_ADMINS

def is_authorized(uid):
    return is_owner(uid) or is_admin_db(uid)

# --- START & HELP ---
@bot.on(events.NewMessage(pattern=r"(?i)^/start"))
async def start(e):
    if not is_authorized(e.sender_id):
        return await e.reply("❌ Aap authorized nahi hain.")
    
    help_msg = """
🌟 **Auto Forward Bot Commands** 🌟

/login - 🔐 Start userbot session
/logout - 🚪 Logout & Delete Session
/cancel - ❌ Cancel current process
/status - ⚡️ View bot status
/on - ✅ Launch the bot
/off - 📴 Close the bot
/setdelay [Sec] - ⏱️ Set delay time
/skip - 🛹 Skip next message
/resume - 🏹 Start forwarding
/addsource [ID] - 📁 Add source chat
/remsource [ID] - 🗑 Remove source
/listsources - 📄 View sources
/addtarget [ID] - ✅ Add target chat
/removetarget [ID] - 😡 Remove target
/listtargets - 🆔 View all targets
/count - 📊 Total forwarded files
/noor - 👀 Detailed status report
/addadmin [ID] - 👤 Add admin (Owner Only)
/restart - ♻️ Restart the bot
    """
    await e.reply(help_msg)

# --- OWNER ONLY COMMAND ---
@bot.on(events.NewMessage(pattern=r"(?i)^/addadmin (\d+)"))
async def add_adm(e):
    if not is_owner(e.sender_id):
        return await e.reply("⛔ Sirf Main Owner (Default Admin) hi admin add kar sakta hai.")
    new_id = int(e.pattern_match.group(1))
    add_admin_db(new_id)
    await e.reply(f"✅ User `{new_id}` authorize ho gaya hai.")

# --- LOGIN & LOGOUT FLOW ---
@bot.on(events.NewMessage(pattern=r"(?i)^/login"))
async def login(e):
    if not is_authorized(e.sender_id): return
    login_state[e.sender_id] = {"step": "phone"}
    await e.reply("📱 Phone number bhejo (+91...):")

@bot.on(events.NewMessage)
async def login_handler(e):
    if e.sender_id not in login_state or e.text.startswith('/'): return
    state = login_state[e.sender_id]
    try:
        if state["step"] == "phone":
            temp_client = TelegramClient(StringSession(), API_ID, API_HASH)
            await temp_client.connect()
            state["phone"] = e.text.strip()
            state["request"] = await temp_client.send_code_request(state["phone"])
            state["client"] = temp_client
            state["step"] = "code"
            await e.reply("✉️ OTP bhejo (Spaces ke saath, e.g., 1 2 3 4 5):")
        elif state["step"] == "code":
            otp = e.text.replace(" ", "")
            try:
                await state["client"].sign_in(state["phone"], otp)
                save_session(e.sender_id, state["client"].session.save())
                login_state.pop(e.sender_id)
                await e.reply("✅ Login Success! /restart karein.")
            except errors.SessionPasswordNeededError:
                state["step"] = "password"
                await e.reply("🔐 2FA Password bhejo:")
        elif state["step"] == "password":
            await state["client"].sign_in(password=e.text.strip())
            save_session(e.sender_id, state["client"].session.save())
            login_state.pop(e.sender_id)
            await e.reply("✅ Login Success! /restart karein.")
    except Exception as err:
        await e.reply(f"❌ Error: {err}")
        login_state.pop(e.sender_id, None)

@bot.on(events.NewMessage(pattern=r"(?i)^/logout"))
async def logout_cmd(e):
    if not is_authorized(e.sender_id): return
    uid = e.sender_id
    delete_session_db(uid)
    if uid in user_clients:
        await user_clients[uid].disconnect()
        del user_clients[uid]
    await e.reply("👋 Logout Success! Session MongoDB se delete ho gaya.")

# --- FORWARDING SETTINGS ---
@bot.on(events.NewMessage(pattern=r"(?i)^/on"))
async def on_cmd(e):
    if not is_authorized(e.sender_id): return
    set_forwarding_db(e.sender_id, True)
    await e.reply("✅ Bot Launch Kar Diya Gaya!")

@bot.on(events.NewMessage(pattern=r"(?i)^/off"))
async def off_cmd(e):
    if not is_authorized(e.sender_id): return
    set_forwarding_db(e.sender_id, False)
    await e.reply("📴 Bot Close Kar Diya Gaya.")

@bot.on(events.NewMessage(pattern=r"(?i)^/setdelay (\d+)"))
async def delay_cmd(e):
    if not is_authorized(e.sender_id): return
    sec = int(e.pattern_match.group(1))
    set_delay_db(e.sender_id, sec)
    await e.reply(f"⏱️ Delay {sec}s par set ho gaya.")

@bot.on(events.NewMessage(pattern=r"(?i)^/skip"))
async def skip_cmd(e):
    if not is_authorized(e.sender_id): return
    skip_next_msg[e.sender_id] = True
    await e.reply("🛹 Agla message skip hoga.")

@bot.on(events.NewMessage(pattern=r"(?i)^/resume"))
async def res_cmd(e):
    if not is_authorized(e.sender_id): return
    set_forwarding_db(e.sender_id, True)
    await e.reply("🏹 Forwarding Resumed.")

# --- SOURCE/TARGET MANAGEMENT ---
@bot.on(events.NewMessage(pattern=r"(?i)^/addsource (-?\d+)"))
async def add_s(e):
    if not is_authorized(e.sender_id): return
    sid = int(e.pattern_match.group(1))
    add_source_db(e.sender_id, sid)
    await e.reply(f"📁 Source {sid} add ho gaya.")

@bot.on(events.NewMessage(pattern=r"(?i)^/remsource (-?\d+)"))
async def rem_s(e):
    if not is_authorized(e.sender_id): return
    sid = int(e.pattern_match.group(1))
    remove_source_db(e.sender_id, sid)
    await e.reply(f"🗑 Source {sid} hat gaya.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listsources"))
async def list_s(e):
    if not is_authorized(e.sender_id): return
    srcs = get_sources(e.sender_id)
    await e.reply(f"📄 Your Sources: `{srcs}`")

@bot.on(events.NewMessage(pattern=r"(?i)^/addtarget (-?\d+)"))
async def add_t(e):
    if not is_authorized(e.sender_id): return
    tid = int(e.pattern_match.group(1))
    add_target(e.sender_id, tid)
    await e.reply(f"✅ Target {tid} add ho gaya.")

@bot.on(events.NewMessage(pattern=r"(?i)^/removetarget (-?\d+)"))
async def rem_t(e):
    if not is_authorized(e.sender_id): return
    tid = int(e.pattern_match.group(1))
    remove_target(e.sender_id, tid)
    await e.reply(f"😡 Target {tid} hat gaya.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listtargets"))
async def list_t(e):
    if not is_authorized(e.sender_id): return
    trgs = get_targets(e.sender_id)
    await e.reply(f"🆔 Your Targets: `{trgs}`")

# --- STATUS & STATS ---
@bot.on(events.NewMessage(pattern=r"(?i)^/status"))
async def status_cmd(e):
    if not is_authorized(e.sender_id): return
    st = "ON ✅" if get_forwarding_db(e.sender_id) else "OFF 📴"
    await e.reply(f"⚡ **Bot Status:** {st}\nDelay: {get_delay(e.sender_id)}s")

@bot.on(events.NewMessage(pattern=r"(?i)^/count"))
async def count_cmd(e):
    if not is_authorized(e.sender_id): return
    await e.reply(f"📊 Total Forwarded: {get_count(e.sender_id)}")

@bot.on(events.NewMessage(pattern=r"(?i)^/noor"))
async def noor_cmd(e):
    if not is_authorized(e.sender_id): return
    msg = f"""
👀 **Detailed Status Report**
👤 ID: `{e.sender_id}`
📈 Count: {get_count(e.sender_id)}
⏱ Delay: {get_delay(e.sender_id)}s
📁 Sources: `{get_sources(e.sender_id)}`
🎯 Targets: `{get_targets(e.sender_id)}`
    """
    await e.reply(msg)

# --- SYSTEM COMMANDS ---
@bot.on(events.NewMessage(pattern=r"(?i)^/restart"))
async def restart(e):
    if not is_authorized(e.sender_id): return
    await e.reply("♻️ Bot Restart ho raha hai...")
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on(events.NewMessage(pattern=r"(?i)^/cancel"))
async def cancel(e):
    login_state.pop(e.sender_id, None)
    await e.reply("❌ Process Cancel Kar Diya Gaya.")

# --- FORWARDER ENGINE ---
async def run_user_clients():
    # KeyError FIX: Purana kharab data filter karein
    sessions = sessions_col.find({"user_id": {"$exists": True}})
    for s in sessions:
        uid = s.get("user_id")
        data = s.get("data")
        if not uid or not data: continue
        try:
            u_client = TelegramClient(StringSession(data), API_ID, API_HASH)
            await u_client.start()
            user_clients[uid] = u_client
            
            @u_client.on(events.NewMessage)
            async def forwarder(ev, current_uid=uid):
                if not get_forwarding_db(current_uid): return
                if ev.chat_id not in get_sources(current_uid): return
                if skip_next_msg.get(current_uid):
                    skip_next_msg[current_uid] = False
                    return
                
                trgs = get_targets(current_uid)
                dly = get_delay(current_uid)
                for t in trgs:
                    if not is_forwarded(current_uid, ev.id, t):
                        try:
                            await ev.client.send_message(t, ev.message)
                            mark_forwarded(current_uid, ev.id, t)
                            inc_count(current_uid)
                            await asyncio.sleep(dly)
                        except: pass
        except: pass

async def main():
    threading.Thread(target=run_web, daemon=True).start()
    await run_user_clients()
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
