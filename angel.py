import os
import sys
import asyncio
import threading
import re
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

def is_owner(uid): return uid in DEFAULT_ADMINS
def is_authorized(uid):
    if is_banned_db(uid): return False
    return is_owner(uid) or is_admin_db(uid)

# --- START & HELP ---
@bot.on(events.NewMessage(pattern=r"(?i)^/start"))
async def start(e):
    if not is_authorized(e.sender_id): return
    msg = """
🌟 **Auto Forward Bot (Complete Edition)** 🌟

**Session Management:**
/login - 🔐 Login with OTP & 2FA
/logout - 🚪 Delete session
/cancel - ❌ Cancel process

**Forwarding Settings:**
/on | /off | /resume - Start/Stop
/status | /noor - Stats & Report
/setdelay [Sec] - Delay manage
/skip - Skip next message

**Content Cleaning (NEW):**
/addfilter [word] - Remove specific word
/remfilter [word] - Delete word filter
/listfilters - List all filters
/endtext [Text] - Add footer
/remendtext - Remove footer
/listendtext - Check footer

**Management:**
/addsource | /remsource | /listsources
/addtarget | /removetarget | /listtargets

**Owner Only:**
/addadmin | /ban | /unban | /removeuser | /restart
    """
    await e.reply(msg)

# --- LOGIN HANDLER (OTP + 2FA) ---
@bot.on(events.NewMessage(pattern=r"(?i)^/login"))
async def login_start(e):
    if not is_authorized(e.sender_id): return
    login_state[e.sender_id] = {"step": "phone"}
    await e.reply("📱 Phone number bhejein (e.g. +919876543210):")

@bot.on(events.NewMessage)
async def handle_all_login(e):
    if e.sender_id not in login_state or e.text.startswith('/'): return
    state = login_state[e.sender_id]
    
    try:
        if state["step"] == "phone":
            temp_client = TelegramClient(StringSession(), API_ID, API_HASH)
            await temp_client.connect()
            phone = e.text.strip()
            state["phone"] = phone
            state["client"] = temp_client
            state["request"] = await temp_client.send_code_request(phone)
            state["step"] = "code"
            await e.reply("✉️ OTP bhejein (Spaces ke saath bhi chalega, e.g. 1 2 3 4 5):")
            
        elif state["step"] == "code":
            otp = e.text.replace(" ", "")
            try:
                await state["client"].sign_in(state["phone"], otp)
                # Success
                save_session(e.sender_id, state["client"].session.save())
                login_state.pop(e.sender_id)
                await e.reply("✅ Login Successful! /restart karein.")
            except errors.SessionPasswordNeededError:
                state["step"] = "2fa"
                await e.reply("🔐 Two-Step Verification (2FA) Password bhejein:")
            except Exception as err:
                await e.reply(f"❌ OTP Error: {err}")
                login_state.pop(e.sender_id)

        elif state["step"] == "2fa":
            password = e.text.strip()
            await state["client"].sign_in(password=password)
            save_session(e.sender_id, state["client"].session.save())
            login_state.pop(e.sender_id)
            await e.reply("✅ 2FA Login Successful! /restart karein.")

    except Exception as general_err:
        await e.reply(f"❌ Error: {general_err}")
        login_state.pop(e.sender_id, None)

# --- ALL OTHER COMMANDS ---
@bot.on(events.NewMessage(pattern=r"(?i)^/logout"))
async def logout(e):
    if not is_authorized(e.sender_id): return
    delete_session_db(e.sender_id)
    await e.reply("🚪 Logout Success.")

@bot.on(events.NewMessage(pattern=r"(?i)^/cancel"))
async def cancel(e):
    login_state.pop(e.sender_id, None)
    await e.reply("❌ Process Cancelled.")

@bot.on(events.NewMessage(pattern=r"(?i)^/(on|resume)"))
async def resume_on(e):
    if not is_authorized(e.sender_id): return
    set_forwarding_db(e.sender_id, True)
    await e.reply("✅ Forwarding ON.")

@bot.on(events.NewMessage(pattern=r"(?i)^/off"))
async def off_cmd(e):
    if not is_authorized(e.sender_id): return
    set_forwarding_db(e.sender_id, False)
    await e.reply("📴 Forwarding OFF.")

@bot.on(events.NewMessage(pattern=r"(?i)^/setdelay (\d+)"))
async def delay_set(e):
    if not is_authorized(e.sender_id): return
    sec = e.pattern_match.group(1)
    set_delay_db(e.sender_id, sec)
    await e.reply(f"⏱ Delay set to {sec}s.")

@bot.on(events.NewMessage(pattern=r"(?i)^/skip"))
async def skip_cmd(e):
    if not is_authorized(e.sender_id): return
    skip_next_msg[e.sender_id] = True
    await e.reply("⏭ Next message skip hoga.")

# --- CONTENT COMMANDS ---
@bot.on(events.NewMessage(pattern=r"(?i)^/addfilter (.*)"))
async def filter_add(e):
    if not is_authorized(e.sender_id): return
    word = e.pattern_match.group(1).strip()
    add_filter_db(e.sender_id, word)
    await e.reply(f"🚫 Word `{word}` added to filters.")

@bot.on(events.NewMessage(pattern=r"(?i)^/remfilter (.*)"))
async def filter_rem(e):
    if not is_authorized(e.sender_id): return
    word = e.pattern_match.group(1).strip()
    rem_filter_db(e.sender_id, word)
    await e.reply(f"🗑 Filter removed for: `{word}`")

@bot.on(events.NewMessage(pattern=r"(?i)^/listfilters"))
async def filter_list(e):
    if not is_authorized(e.sender_id): return
    words = get_filters_db(e.sender_id)
    await e.reply(f"📋 **Active Filters:**\n`{', '.join(words) if words else 'None'}`")

@bot.on(events.NewMessage(pattern=r"(?i)^/endtext (.*)"))
async def et_set(e):
    if not is_authorized(e.sender_id): return
    txt = e.pattern_match.group(1).strip()
    set_endtext_db(e.sender_id, txt)
    await e.reply("📝 Endtext set.")

@bot.on(events.NewMessage(pattern=r"(?i)^/remendtext"))
async def et_rem(e):
    if not is_authorized(e.sender_id): return
    rem_endtext_db(e.sender_id)
    await e.reply("🗑 Endtext removed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listendtext"))
async def et_list(e):
    if not is_authorized(e.sender_id): return
    et = get_endtext_db(e.sender_id)
    await e.reply(f"📄 **Footer:**\n`{et if et else 'Not Set'}`")

# --- SOURCE/TARGET MGMT ---
@bot.on(events.NewMessage(pattern=r"(?i)^/addsource (-?\d+)"))
async def asrc(e):
    if not is_authorized(e.sender_id): return
    add_source_db(e.sender_id, int(e.pattern_match.group(1)))
    await e.reply("✅ Source Added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/remsource (-?\d+)"))
async def rsrc(e):
    if not is_authorized(e.sender_id): return
    remove_source_db(e.sender_id, int(e.pattern_match.group(1)))
    await e.reply("🗑 Source Removed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listsources"))
async def lsrc(e):
    if not is_authorized(e.sender_id): return
    await e.reply(f"📄 **Sources:**\n`{get_sources(e.sender_id)}`")

@bot.on(events.NewMessage(pattern=r"(?i)^/addtarget (-?\d+)"))
async def atgt(e):
    if not is_authorized(e.sender_id): return
    add_target_db(e.sender_id, int(e.pattern_match.group(1)))
    await e.reply("🎯 Target Added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/removetarget (-?\d+)"))
async def rtgt(e):
    if not is_authorized(e.sender_id): return
    remove_target_db(e.sender_id, int(e.pattern_match.group(1)))
    await e.reply("🗑 Target Removed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listtargets"))
async def ltgt(e):
    if not is_authorized(e.sender_id): return
    await e.reply(f"🎯 **Targets:**\n`{get_targets(e.sender_id)}`")

# --- STATS & ADMIN ---
@bot.on(events.NewMessage(pattern=r"(?i)^/count"))
async def count_c(e):
    if not is_authorized(e.sender_id): return
    await e.reply(f"📊 Total Count: {get_count_db(e.sender_id)}")

@bot.on(events.NewMessage(pattern=r"(?i)^/(status|noor)"))
async def status_r(e):
    if not is_authorized(e.sender_id): return
    uid = e.sender_id
    msg = (f"📈 **Report**\nForwarding: {get_forwarding_db(uid)}\n"
           f"Delay: {get_delay(uid)}s\nCount: {get_count_db(uid)}\n"
           f"Filters: {len(get_filters_db(uid))}\nEndtext: {'Yes' if get_endtext_db(uid) else 'No'}")
    await e.reply(msg)

@bot.on(events.NewMessage(pattern=r"(?i)^/addadmin (\d+)"))
async def aadmin(e):
    if not is_owner(e.sender_id): return
    add_admin_db(int(e.pattern_match.group(1)))
    await e.reply("👤 Admin added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/ban (\d+)"))
async def banu(e):
    if not is_owner(e.sender_id): return
    ban_user_db(int(e.pattern_match.group(1)))
    await e.reply("🚫 User banned.")

@bot.on(events.NewMessage(pattern=r"(?i)^/restart"))
async def rest(e):
    if not is_authorized(e.sender_id): return
    await e.reply("♻ Restarting...")
    os.execl(sys.executable, sys.executable, *sys.argv)

# --- ENGINE ---
async def start_engine():
    all_s = get_all_sessions()
    for s in all_s:
        uid, token = s["user_id"], s["data"]
        if is_banned_db(uid): continue
        try:
            client = TelegramClient(StringSession(token), API_ID, API_HASH)
            await client.start()
            user_clients[uid] = client
            
            @client.on(events.NewMessage)
            async def forwarder(ev, c_uid=uid):
                if not get_forwarding_db(c_uid) or ev.chat_id not in get_sources(c_uid): return
                if skip_next_msg.get(c_uid):
                    skip_next_msg[c_uid] = False
                    return
                
                # Cleaning
                text = ev.text or ""
                text = re.sub(r'https?://\S+|t\.me/\S+', '', text) # Links
                for w in get_filters_db(c_uid): text = re.compile(re.escape(w), re.IGNORECASE).sub('', text) # Word Filters
                
                # Footer
                footer = get_endtext_db(c_uid)
                final = f"{text.strip()}\n\n{footer}" if footer else text.strip()
                
                for t in get_targets(c_uid):
                    if not is_forwarded(c_uid, ev.id, t):
                        try:
                            await ev.client.send_message(t, final, file=ev.media)
                            mark_forwarded(c_uid, ev.id, t)
                            inc_count(c_uid)
                            await asyncio.sleep(get_delay(c_uid))
                        except: pass
        except: pass

async def main():
    threading.Thread(target=run_web, daemon=True).start()
    await start_engine()
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
