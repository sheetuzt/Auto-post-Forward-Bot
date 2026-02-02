import os
import sys
import asyncio
import threading
from flask import Flask
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
from angel_db import *

# Web health check for deployment
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
# Aapka Telegram ID .env mein DEFAULT_ADMINS mein hona chahiye
DEFAULT_ADMINS = [int(x.strip()) for x in os.getenv("DEFAULT_ADMINS", "").split(",") if x.strip()]

bot = TelegramClient("bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Active UserBot Clients
user_clients = {}
login_state = {}
skip_next_msg = {}

# --- HELPER FUNCTIONS ---
def is_owner(uid):
    return uid in DEFAULT_ADMINS

def is_authorized(uid):
    return is_owner(uid) or is_admin_db(uid)

# --- START & HELP ---
@bot.on(events.NewMessage(pattern=r"(?i)^/start"))
async def start(e):
    if not is_authorized(e.sender_id):
        return await e.reply("❌ Aap authorized nahi hain. Owner se sampark karein.")
    
    msg = """
🌟 **Auto Forward Bot Commands** 🌟

/login - 🔐 Start userbot session
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
/addadmin [ID] - 👤 Add new admin (Owner Only)
/restart - ♻️ Restart the bot
/cancel - ❌ Cancel process
    """
    await e.reply(msg)

# --- OWNER ONLY COMMANDS ---
@bot.on(events.NewMessage(pattern=r"(?i)^/addadmin (\d+)"))
async def add_admin(e):
    if not is_owner(e.sender_id):
        return await e.reply("⛔ Sirf Owner hi naye admins add kar sakta hai.")
    new_id = int(e.pattern_match.group(1))
    add_admin_db(new_id)
    await e.reply(f"✅ User {new_id} ko authorize kar diya gaya hai.")

@bot.on(events.NewMessage(pattern=r"(?i)^/remadmin (\d+)"))
async def rem_admin(e):
    if not is_owner(e.sender_id): return
    target_id = int(e.pattern_match.group(1))
    remove_admin_db(target_id)
    await e.reply(f"❌ User {target_id} ki authorization hata di gayi hai.")

# --- LOGIN FLOW ---
@bot.on(events.NewMessage(pattern=r"(?i)^/login"))
async def login(e):
    if not is_authorized(e.sender_id): return
    login_state[e.sender_id] = {"step": "phone"}
    await e.reply("📱 Apna Phone number international format mein bhejo (e.g., +919876543210)")

@bot.on(events.NewMessage)
async def handle_login(e):
    if e.sender_id not in login_state or e.text.startswith('/'): return
    state = login_state[e.sender_id]
    
    try:
        if state["step"] == "phone":
            temp_client = TelegramClient(StringSession(), API_ID, API_HASH)
            await temp_client.connect()
            phone = e.text.strip()
            state["phone"] = phone
            state["request"] = await temp_client.send_code_request(phone)
            state["client"] = temp_client
            state["step"] = "code"
            await e.reply("✉️ OTP bhejo (Spaces ke saath, e.g., 1 2 3 4 5)")
        
        elif state["step"] == "code":
            otp = e.text.replace(" ", "")
            try:
                await state["client"].sign_in(state["phone"], otp)
                save_session(e.sender_id, state["client"].session.save())
                login_state.pop(e.sender_id)
                await e.reply("✅ Login Successful! /restart karein.")
            except errors.SessionPasswordNeededError:
                state["step"] = "password"
                await e.reply("🔐 2FA Password bhejo:")
        
        elif state["step"] == "password":
            await state["client"].sign_in(password=e.text.strip())
            save_session(e.sender_id, state["client"].session.save())
            login_state.pop(e.sender_id)
            await e.reply("✅ Login Successful with 2FA! /restart karein.")
    except Exception as err:
        await e.reply(f"❌ Error: {err}")
        login_state.pop(e.sender_id, None)

# --- MANAGEMENT COMMANDS ---
@bot.on(events.NewMessage(pattern=r"(?i)^/addsource (-?\d+)"))
async def add_src(e):
    if not is_authorized(e.sender_id): return
    sid = int(e.pattern_match.group(1))
    add_source_db(e.sender_id, sid)
    await e.reply(f"✅ Source {sid} added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/remsource (-?\d+)"))
async def rem_src(e):
    if not is_authorized(e.sender_id): return
    sid = int(e.pattern_match.group(1))
    remove_source_db(e.sender_id, sid)
    await e.reply(f"🗑 Source {sid} removed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listsources"))
async def list_src(e):
    if not is_authorized(e.sender_id): return
    srcs = get_sources(e.sender_id)
    await e.reply(f"📄 **Your Sources:**\n`{srcs}`")

@bot.on(events.NewMessage(pattern=r"(?i)^/addtarget (-?\d+)"))
async def add_trg(e):
    if not is_authorized(e.sender_id): return
    tid = int(e.pattern_match.group(1))
    add_target(e.sender_id, tid)
    await e.reply(f"✅ Target {tid} added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/removetarget (-?\d+)"))
async def rem_trg(e):
    if not is_authorized(e.sender_id): return
    tid = int(e.pattern_match.group(1))
    remove_target(e.sender_id, tid)
    await e.reply(f"🗑 Target {tid} removed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listtargets"))
async def list_trg(e):
    if not is_authorized(e.sender_id): return
    trgs = get_targets(e.sender_id)
    await e.reply(f"🆔 **Your Targets:**\n`{trgs}`")

@bot.on(events.NewMessage(pattern=r"(?i)^/setdelay (\d+)"))
async def set_delay_cmd(e):
    if not is_authorized(e.sender_id): return
    sec = int(e.pattern_match.group(1))
    set_delay_db(e.sender_id, sec)
    await e.reply(f"⏱ Delay set to {sec}s.")

@bot.on(events.NewMessage(pattern=r"(?i)^/on"))
async def on_cmd(e):
    if not is_authorized(e.sender_id): return
    set_forwarding_db(e.sender_id, True)
    await e.reply("✅ Bot launched for you!")

@bot.on(events.NewMessage(pattern=r"(?i)^/off"))
async def off_cmd(e):
    if not is_authorized(e.sender_id): return
    set_forwarding_db(e.sender_id, False)
    await e.reply("📴 Bot closed for you.")

@bot.on(events.NewMessage(pattern=r"(?i)^/skip"))
async def skip_cmd(e):
    if not is_authorized(e.sender_id): return
    skip_next_msg[e.sender_id] = True
    await e.reply("🛹 Next message will be skipped.")

@bot.on(events.NewMessage(pattern=r"(?i)^/resume"))
async def resume_cmd(e):
    if not is_authorized(e.sender_id): return
    set_forwarding_db(e.sender_id, True)
    await e.reply("🏹 Forwarding Resumed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/status"))
async def status_cmd(e):
    if not is_authorized(e.sender_id): return
    active = "ON ✅" if get_forwarding_db(e.sender_id) else "OFF 📴"
    await e.reply(f"⚡ **Status:** {active}\n📁 Sources: {len(get_sources(e.sender_id))}\n🎯 Targets: {len(get_targets(e.sender_id))}")

@bot.on(events.NewMessage(pattern=r"(?i)^/count"))
async def count_cmd(e):
    if not is_authorized(e.sender_id): return
    await e.reply(f"📊 Total forwarded: {get_count(e.sender_id)}")

@bot.on(events.NewMessage(pattern=r"(?i)^/noor"))
async def noor_cmd(e):
    if not is_authorized(e.sender_id): return
    msg = f"""
👀 **Detailed Report**
👤 User ID: `{e.sender_id}`
📈 Total Forwarded: {get_count(e.sender_id)}
⏱ Current Delay: {get_delay(e.sender_id)}s
📁 Sources: `{get_sources(e.sender_id)}`
🎯 Targets: `{get_targets(e.sender_id)}`
    """
    await e.reply(msg)

@bot.on(events.NewMessage(pattern=r"(?i)^/restart"))
async def restart_cmd(e):
    if not is_authorized(e.sender_id): return
    await e.reply("♻️ Restarting...")
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on(events.NewMessage(pattern=r"(?i)^/cancel"))
async def cancel_cmd(e):
    login_state.pop(e.sender_id, None)
    await e.reply("❌ Process cancelled.")

# --- FORWARDER ENGINE ---
async def run_user_clients():
    sessions = sessions_col.find()
    for s in sessions:
        uid = s["user_id"]
        client_str = s["data"]
        try:
            u_client = TelegramClient(StringSession(client_str), API_ID, API_HASH)
            await u_client.start()
            user_clients[uid] = u_client
            print(f"Started UserBot for {uid}")

            @u_client.on(events.NewMessage)
            async def forwarder_handler(event, current_uid=uid):
                # Is user ne forwarding ON ki hai?
                if not get_forwarding_db(current_uid): return
                
                # Kya message source channel se hai?
                sources = get_sources(current_uid)
                if event.chat_id not in sources: return

                # Kya skip command active hai?
                if skip_next_msg.get(current_uid):
                    skip_next_msg[current_uid] = False
                    return

                targets = get_targets(current_uid)
                delay = get_delay(current_uid)

                for t in targets:
                    if not is_forwarded(current_uid, event.id, t):
                        try:
                            await event.client.send_message(t, event.message)
                            mark_forwarded(current_uid, event.id, t)
                            inc_count(current_uid)
                            await asyncio.sleep(delay)
                        except Exception as ex:
                            print(f"Error for {current_uid}: {ex}")

        except Exception as e:
            print(f"Could not start {uid}: {e}")

async def main():
    threading.Thread(target=run_web, daemon=True).start()
    await run_user_clients()
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
