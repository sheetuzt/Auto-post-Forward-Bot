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

# --- HELPER: TEXT CLEANER ---
def clean_text(text, uid):
    if not text: return ""
    text = re.sub(r'https?://\S+|t\.me/\S+', '', text) # Links remove
    for word in get_filters_db(uid):
        text = re.compile(re.escape(word), re.IGNORECASE).sub('', text) # Word filters
    footer = get_endtext_db(uid)
    return f"{text.strip()}\n\n{footer}".strip() if footer else text.strip()

# --- START & HELP ---
@bot.on(events.NewMessage(pattern=r"(?i)^/start"))
async def start(e):
    if not is_authorized(e.sender_id): return
    msg = """
🌟 **Auto Forward Bot (Master Edition)** 🌟

**Session:** /login | /logout | /cancel
**Forwarding:** /on | /off | /resume | /status | /noor
**Settings:** /setdelay [Sec] | /skip
**Filter:** /addfilter [word] | /remfilter [word] | /listfilters
**Footer:** /endtext [Text] | /remendtext | /listendtext
**Management:** /addsource | /remsource | /listsources | /addtarget | /removetarget | /listtargets
**Admin:** /addadmin | /ban | /unban | /removeuser | /restart | /count
    """
    await e.reply(msg)

# --- LOGIN (OTP + 2FA) ---
@bot.on(events.NewMessage(pattern=r"(?i)^/login"))
async def login_start(e):
    if not is_authorized(e.sender_id): return
    login_state[e.sender_id] = {"step": "phone"}
    await e.reply("📱 Phone number bhejein (e.g. +919876543210):")

@bot.on(events.NewMessage)
async def handle_login(e):
    if e.sender_id not in login_state or e.text.startswith('/'): return
    state = login_state[e.sender_id]
    try:
        if state["step"] == "phone":
            temp_client = TelegramClient(StringSession(), API_ID, API_HASH)
            await temp_client.connect()
            state["phone"], state["client"] = e.text.strip(), temp_client
            state["request"] = await temp_client.send_code_request(state["phone"])
            state["step"] = "code"
            await e.reply("✉️ OTP bhejein (Spaces allowed, e.g. 1 2 3 4 5):")
        elif state["step"] == "code":
            otp = e.text.replace(" ", "")
            try:
                await state["client"].sign_in(state["phone"], otp)
                save_session(e.sender_id, state["client"].session.save())
                login_state.pop(e.sender_id)
                await e.reply("✅ Login Success! /restart karein.")
            except errors.SessionPasswordNeededError:
                state["step"] = "2fa"
                await e.reply("🔐 2FA Password bhejein:")
        elif state["step"] == "2fa":
            await state["client"].sign_in(password=e.text.strip())
            save_session(e.sender_id, state["client"].session.save())
            login_state.pop(e.sender_id)
            await e.reply("✅ Login Success! /restart karein.")
    except Exception as err:
        await e.reply(f"❌ Error: {err}")
        login_state.pop(e.sender_id, None)

# --- FORWARDING ENGINE (Album + Single Fix) ---
async def start_engine():
    all_s = get_all_sessions()
    for s in all_s:
        uid, token = s["user_id"], s["data"]
        try:
            client = TelegramClient(StringSession(token), API_ID, API_HASH)
            await client.start()
            user_clients[uid] = client

            # ALBUM HANDLER (For 5+ Photos)
            @client.on(events.Album)
            async def album_handler(ev, c_uid=uid):
                if not get_forwarding_db(c_uid) or ev.chat_id not in get_sources(c_uid): return
                new_caption = clean_text(ev.text, c_uid)
                for t in get_targets(c_uid):
                    try:
                        await ev.client.send_file(t, ev.messages, caption=new_caption)
                        inc_count(c_uid)
                        await asyncio.sleep(get_delay(c_uid))
                    except: pass

            # SINGLE MESSAGE HANDLER
            @client.on(events.NewMessage(func=lambda ev: not ev.grouped_id))
            async def single_handler(ev, c_uid=uid):
                if not get_forwarding_db(c_uid) or ev.chat_id not in get_sources(c_uid): return
                if skip_next_msg.get(c_uid):
                    skip_next_msg[c_uid] = False
                    return
                new_text = clean_text(ev.text, c_uid)
                for t in get_targets(c_uid):
                    if not is_forwarded(c_uid, ev.id, t):
                        try:
                            await ev.client.send_message(t, new_text, file=ev.media)
                            mark_forwarded(c_uid, ev.id, t)
                            inc_count(c_uid)
                            await asyncio.sleep(get_delay(c_uid))
                        except: pass
        except: pass

# --- ALL COMMAND HANDLERS ---
@bot.on(events.NewMessage(pattern=r"(?i)^/logout"))
async def logout(e):
    if is_authorized(e.sender_id):
        delete_session_db(e.sender_id)
        await e.reply("🚪 Logout Success.")

@bot.on(events.NewMessage(pattern=r"(?i)^/cancel"))
async def cancel(e):
    login_state.pop(e.sender_id, None)
    await e.reply("❌ Cancelled.")

@bot.on(events.NewMessage(pattern=r"(?i)^/(on|resume)"))
async def resume_cmd(e):
    if is_authorized(e.sender_id):
        set_forwarding_db(e.sender_id, True)
        await e.reply("▶️ Forwarding Resumed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/off"))
async def off_cmd(e):
    if is_authorized(e.sender_id):
        set_forwarding_db(e.sender_id, False)
        await e.reply("📴 Forwarding Stopped.")

@bot.on(events.NewMessage(pattern=r"(?i)^/setdelay (\d+)"))
async def delay_set(e):
    if is_authorized(e.sender_id):
        sec = e.pattern_match.group(1)
        set_delay_db(e.sender_id, sec)
        await e.reply(f"⏱ Delay: {sec}s.")

@bot.on(events.NewMessage(pattern=r"(?i)^/skip"))
async def skip_cmd(e):
    if is_authorized(e.sender_id):
        skip_next_msg[e.sender_id] = True
        await e.reply("⏭ Next message skip hoga.")

# --- FILTERS & ENDTEXT ---
@bot.on(events.NewMessage(pattern=r"(?i)^/addfilter (.*)"))
async def flt_add(e):
    if is_authorized(e.sender_id):
        add_filter_db(e.sender_id, e.pattern_match.group(1).strip())
        await e.reply("✅ Filter added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/remfilter (.*)"))
async def flt_rem(e):
    if is_authorized(e.sender_id):
        rem_filter_db(e.sender_id, e.pattern_match.group(1).strip())
        await e.reply("🗑 Filter removed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listfilters"))
async def flt_list(e):
    if is_authorized(e.sender_id):
        w = get_filters_db(e.sender_id)
        await e.reply(f"📋 Filters: `{', '.join(w) if w else 'None'}`")

@bot.on(events.NewMessage(pattern=r"(?i)^/endtext (.*)"))
async def et_set(e):
    if is_authorized(e.sender_id):
        set_endtext_db(e.sender_id, e.pattern_match.group(1).strip())
        await e.reply("📝 Endtext set.")

@bot.on(events.NewMessage(pattern=r"(?i)^/remendtext"))
async def et_rem(e):
    if is_authorized(e.sender_id):
        rem_endtext_db(e.sender_id)
        await e.reply("🗑 Endtext removed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listendtext"))
async def et_list(e):
    if is_authorized(e.sender_id):
        et = get_endtext_db(e.sender_id)
        await e.reply(f"📄 Footer: `{et if et else 'Not Set'}`")

# --- SOURCE/TARGET ---
@bot.on(events.NewMessage(pattern=r"(?i)^/addsource (-?\d+)"))
async def asrc(e):
    if is_authorized(e.sender_id):
        add_source_db(e.sender_id, int(e.pattern_match.group(1)))
        await e.reply("✅ Source added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/remsource (-?\d+)"))
async def rsrc(e):
    if is_authorized(e.sender_id):
        remove_source_db(e.sender_id, int(e.pattern_match.group(1)))
        await e.reply("🗑 Source removed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listsources"))
async def lsrc(e):
    if is_authorized(e.sender_id):
        await e.reply(f"📄 Sources: `{get_sources(e.sender_id)}`")

@bot.on(events.NewMessage(pattern=r"(?i)^/addtarget (-?\d+)"))
async def atgt(e):
    if is_authorized(e.sender_id):
        add_target_db(e.sender_id, int(e.pattern_match.group(1)))
        await e.reply("🎯 Target added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/removetarget (-?\d+)"))
async def rtgt(e):
    if is_authorized(e.sender_id):
        remove_target_db(e.sender_id, int(e.pattern_match.group(1)))
        await e.reply("🗑 Target removed.")

@bot.on(events.NewMessage(pattern=r"(?i)^/listtargets"))
async def ltgt(e):
    if is_authorized(e.sender_id):
        await e.reply(f"🎯 Targets: `{get_targets(e.sender_id)}`")

# --- ADMIN & STATS ---
@bot.on(events.NewMessage(pattern=r"(?i)^/count"))
async def count_cmd(e):
    if is_authorized(e.sender_id):
        await e.reply(f"📊 Total: {get_count_db(e.sender_id)}")

@bot.on(events.NewMessage(pattern=r"(?i)^/(status|noor)"))
async def status_cmd(e):
    if is_authorized(e.sender_id):
        uid = e.sender_id
        rep = (f"📈 **Status**\nForwarding: {get_forwarding_db(uid)}\n"
               f"Delay: {get_delay(uid)}s\nCount: {get_count_db(uid)}\n"
               f"Sources: {len(get_sources(uid))}\nTargets: {len(get_targets(uid))}")
        await e.reply(rep)

@bot.on(events.NewMessage(pattern=r"(?i)^/addadmin (\d+)"))
async def aadmin(e):
    if is_owner(e.sender_id):
        add_admin_db(int(e.pattern_match.group(1)))
        await e.reply("👤 Admin added.")

@bot.on(events.NewMessage(pattern=r"(?i)^/ban (\d+)"))
async def banu(e):
    if is_owner(e.sender_id):
        ban_user_db(int(e.pattern_match.group(1)))
        await e.reply("🚫 Banned.")

@bot.on(events.NewMessage(pattern=r"(?i)^/unban (\d+)"))
async def ubanu(e):
    if is_owner(e.sender_id):
        unban_user_db(int(e.pattern_match.group(1)))
        await e.reply("😇 Unbanned.")

@bot.on(events.NewMessage(pattern=r"(?i)^/removeuser (\d+)"))
async def remu(e):
    if is_owner(e.sender_id):
        full_remove_user_db(int(e.pattern_match.group(1)))
        await e.reply("🗑 User data wiped.")

@bot.on(events.NewMessage(pattern=r"(?i)^/restart"))
async def restart_bot(e):
    if is_authorized(e.sender_id):
        await e.reply("♻ Restarting...")
        os.execl(sys.executable, sys.executable, *sys.argv)

# --- MAIN ---
async def main():
    threading.Thread(target=run_web, daemon=True).start()
    await start_engine()
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
