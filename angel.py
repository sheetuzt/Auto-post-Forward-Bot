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
user_clients = {} 
login_state = {}
skip_next_msg = {}

# --- AUTH CHECKS ---
def is_owner(uid): return uid in DEFAULT_ADMINS
def is_authorized(uid):
    if is_banned_db(uid): return False
    return is_owner(uid) or is_admin_db(uid)

# --- START & HELP ---
@bot.on(events.NewMessage(pattern=r"(?i)^/start"))
async def start(e):
    if not is_authorized(e.sender_id): return await e.reply("❌ Unauthorized.")
    
    msg = """
🌟 **Auto Forward Bot (Complete)** 🌟

**Session:**
/login - 🔐 Account login karein
/logout - 🚪 Session delete karein
/cancel - ❌ Current process stop karein

**Settings:**
/on | /off - ✅ Forwarding chalu/band
/setdelay [Sec] - ⏱ Delay set karein
/skip - 🛹 Agla message skip karein
/resume - 🏹 Forwarding firse chalu karein

**Management:**
/addsource [ID] | /remsource [ID]
/listsources - 📄 Sources dekhein
/addtarget [ID] | /removetarget [ID]
/listtargets - 🎯 Targets dekhein

**Stats:**
/count - 📊 Total messages count
/noor - 👀 Detailed Report
/status - ⚡ Bot status

**Owner Only:**
/addadmin [ID] - 👤 Naya admin banayein
/ban [ID] - 🚫 User ban karein
/unban [ID] - 😇 User unban karein
/removeuser [ID] - 🗑 User data wipe karein
/restart - ♻ Bot restart karein
    """
    await e.reply(msg)

# --- OWNER COMMANDS ---
@bot.on(events.NewMessage(pattern=r"(?i)^/addadmin (\d+)"))
async def add_adm(e):
    if not is_owner(e.sender_id): return
    uid = int(e.pattern_match.group(1))
    add_admin_db(uid)
    await e.reply(f"✅ User `{uid}` ko admin bana diya gaya.")

@bot.on(events.NewMessage(pattern=r"(?i)^/ban (\d+)"))
async def ban_u(e):
    if not is_owner(e.sender_id): return
    uid = int(e.pattern_match.group(1))
    ban_user_db(uid)
    if uid in user_clients:
        await user_clients[uid].disconnect()
        del user_clients[uid]
    await e.reply(f"🚫 User `{uid}` BANNED.")

@bot.on(events.NewMessage(pattern=r"(?i)^/unban (\d+)"))
async def unban_u(e):
    if not is_owner(e.sender_id): return
    uid = int(e.pattern_match.group(1))
    unban_user_db(uid)
    await e.reply(f"😇 User `{uid}` UNBANNED.")

@bot.on(events.NewMessage(pattern=r"(?i)^/removeuser (\d+)"))
async def rem_u(e):
    if not is_owner(e.sender_id): return
    uid = int(e.pattern_match.group(1))
    full_remove_user_db(uid)
    if uid in user_clients:
        await user_clients[uid].disconnect()
        del user_clients[uid]
    await e.reply(f"🗑 User `{uid}` ka data wipe kar diya gaya.")

# --- SESSION MGMT ---
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
            temp = TelegramClient(StringSession(), API_ID, API_HASH)
            await temp.connect()
            state["phone"] = e.text.strip()
            state["request"] = await temp.send_code_request(state["phone"])
            state["client"] = temp
            state["step"] = "code"
            await e.reply("✉ OTP (Space ke saath, e.g. 1 2 3 4 5):")
        elif state["step"] == "code":
            otp = e.text.replace(" ", "")
            try:
                await state["client"].sign_in(state["phone"], otp)
                save_session(e.sender_id, state["client"].session.save())
                login_state.pop(e.sender_id)
                await e.reply("✅ Login Success! /restart karein.")
            except errors.SessionPasswordNeededError:
                state["step"] = "password"
                await e.reply("🔐 2FA Password:")
        elif state["step"] == "password":
            await state["client"].sign_in(password=e.text.strip())
            save_session(e.sender_id, state["client"].session.save())
            login_state.pop(e.sender_id)
            await e.reply("✅ Login Success! /restart.")
    except Exception as err:
        await e.reply(f"❌ Error: {err}")
        login_state.pop(e.sender_id, None)

@bot.on(events.NewMessage(pattern=r"(?i)^/logout"))
async def logout(e):
    if not is_authorized(e.sender_id): return
    delete_session_db(e.sender_id)
    if e.sender_id in user_clients:
        await user_clients[e.sender_id].disconnect()
        del user_clients[e.sender_id]
    await e.reply("🚪 Logout Success! Session deleted from DB.")

# --- SETTINGS COMMANDS ---
@bot.on(events.NewMessage(pattern=r"(?i)^/on"))
async def on_f(e):
    if not is_authorized(e.sender_id): return
    set_forwarding_db(e.sender_id, True)
    await e.reply("✅ Forwarding ON")

@bot.on(events.NewMessage(pattern=r"(?i)^/off"))
async def off_f(e):
    if not is_authorized(e.sender_id): return
    set_forwarding_db(e.sender_id, False)
    await e.reply("📴 Forwarding OFF")

@bot.on(events.NewMessage(pattern=r"(?i)^/setdelay (\d+)"))
async def delay(e):
    if not is_authorized(e.sender_id): return
    sec = int(e.pattern_match.group(1))
    set_delay_db(e.sender_id, sec)
    await e.reply(f"⏱ Delay set to {sec}s")

@bot.on(events.NewMessage(pattern=r"(?i)^/skip"))
async def skip(e):
    if not is_authorized(e.sender_id): return
    skip_next_msg[e.sender_id] = True
    await e.reply("🛹 Next message skip hoga.")

# --- SOURCE/TARGET MGMT ---
@bot.on(events.NewMessage(pattern=r"(?i)^/addsource (-?\d+)"))
async def add_s(e):
    if not is_authorized(e.sender_id): return
    add_source_db(e.sender_id, int(e.pattern_match.group(1)))
    await e.reply("📁 Source Added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/remsource (-?\d+)"))
async def rem_s(e):
    if not is_authorized(e.sender_id): return
    remove_source_db(e.sender_id, int(e.pattern_match.group(1)))
    await e.reply("🗑 Source Removed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listsources"))
async def list_s(e):
    if not is_authorized(e.sender_id): return
    await e.reply(f"📄 Sources: `{get_sources(e.sender_id)}`")

@bot.on(events.NewMessage(pattern=r"(?i)^/addtarget (-?\d+)"))
async def add_t(e):
    if not is_authorized(e.sender_id): return
    add_target(e.sender_id, int(e.pattern_match.group(1)))
    await e.reply("🎯 Target Added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/removetarget (-?\d+)"))
async def rem_t(e):
    if not is_authorized(e.sender_id): return
    remove_target(e.sender_id, int(e.pattern_match.group(1)))
    await e.reply("😡 Target Removed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listtargets"))
async def list_t(e):
    if not is_authorized(e.sender_id): return
    await e.reply(f"🆔 Targets: `{get_targets(e.sender_id)}`")

# --- STATS ---
@bot.on(events.NewMessage(pattern=r"(?i)^/count"))
async def count(e):
    if not is_authorized(e.sender_id): return
    await e.reply(f"📊 Total: {get_count(e.sender_id)}")

@bot.on(events.NewMessage(pattern=r"(?i)^/noor"))
async def noor(e):
    if not is_authorized(e.sender_id): return
    msg = f"👤 ID: `{e.sender_id}`\n📈 Count: {get_count(e.sender_id)}\n⏱ Delay: {get_delay(e.sender_id)}s\n📁 Src: {len(get_sources(e.sender_id))}\n🎯 Trg: {len(get_targets(e.sender_id))}"
    await e.reply(msg)

# --- SYSTEM ---
@bot.on(events.NewMessage(pattern=r"(?i)^/restart"))
async def restart(e):
    if not is_authorized(e.sender_id): return
    await e.reply("♻ Restarting...")
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on(events.NewMessage(pattern=r"(?i)^/cancel"))
async def cancel(e):
    login_state.pop(e.sender_id, None)
    await e.reply("❌ Cancelled.")

# --- FORWARDER ENGINE ---
async def run_user_clients():
    sessions = sessions_col.find({"user_id": {"$exists": True}})
    for s in sessions:
        uid = s.get("user_id")
        if is_banned_db(uid): continue
        token = s.get("data")
        if not uid or not token: continue
        try:
            u_client = TelegramClient(StringSession(token), API_ID, API_HASH)
            await u_client.start()
            user_clients[uid] = u_client
            
            @u_client.on(events.NewMessage)
            async def h(ev, c_uid=uid):
                if not get_forwarding_db(c_uid): return
                if ev.chat_id not in get_sources(c_uid): return
                if skip_next_msg.get(c_uid):
                    skip_next_msg[c_uid] = False
                    return
                for t in get_targets(c_uid):
                    if not is_forwarded(c_uid, ev.id, t):
                        try:
                            await ev.client.send_message(t, ev.message)
                            mark_forwarded(c_uid, ev.id, t)
                            inc_count(c_uid)
                            await asyncio.sleep(get_delay(c_uid))
                        except: pass
        except Exception as e: print(f"Client {uid} Error: {e}")

async def main():
    threading.Thread(target=run_web, daemon=True).start()
    await run_user_clients()
    print("Bot is running...")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
