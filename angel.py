import os
import asyncio
from telethon import TelegramClient, events
from angel_db import (
    get_targets, add_target, remove_target,
    add_admin, remove_admin, get_admins,
    get_delay, set_delay, inc_count, get_count
)

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = TelegramClient("bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)
user = TelegramClient("user", API_ID, API_HASH)

login_state = {}
forwarding_on = False
skip_next = False


# -------------------- HELPERS --------------------

def is_admin_user(uid):
    return uid in get_admins()


# -------------------- START --------------------

@bot.on(events.NewMessage(pattern="/start"))
async def start(event):
    await event.reply("🤖 Auto Forward Bot Ready\n/login to connect account")


# -------------------- LOGIN --------------------

@bot.on(events.NewMessage(pattern="/login"))
async def login_cmd(event):
    login_state[event.sender_id] = {"step": "phone"}
    await event.reply("📱 Send phone with country code\nExample: +919876543210")


@bot.on(events.NewMessage(func=lambda e: e.is_private and not e.raw_text.startswith("/")))
async def login_flow(event):
    if event.sender_id not in login_state:
        return

    state = login_state[event.sender_id]
    text = event.raw_text.strip()

    if state["step"] == "phone":
        if not text.startswith("+"):
            return await event.reply("❌ Invalid phone format")

        state["phone"] = text
        state["step"] = "otp"

        await user.connect()
        await user.send_code_request(text)
        return await event.reply("🔑 OTP sent. Send OTP")

    if state["step"] == "otp":
        try:
            await user.sign_in(state["phone"], text)
            await event.reply("✅ Login success. Restarting...")
            os._exit(0)
        except Exception as e:
            await event.reply(f"❌ OTP Error {e}")


# -------------------- BASIC CONTROLS --------------------

@bot.on(events.NewMessage(pattern="/on"))
async def on_cmd(event):
    global forwarding_on
    forwarding_on = True
    await event.reply("✅ Forwarding ON")


@bot.on(events.NewMessage(pattern="/off"))
async def off_cmd(event):
    global forwarding_on
    forwarding_on = False
    await event.reply("🛑 Forwarding OFF")


@bot.on(events.NewMessage(pattern="/status"))
async def status(event):
    await event.reply(f"⚡ Forwarding: {forwarding_on}\nDelay: {get_delay()} sec")


@bot.on(events.NewMessage(pattern="/restart"))
async def restart(event):
    await event.reply("♻️ Restarting...")
    os._exit(0)


# -------------------- DELAY --------------------

@bot.on(events.NewMessage(pattern="/setdelay"))
async def setdelay(event):
    if not is_admin_user(event.sender_id):
        return
    sec = int(event.raw_text.split()[-1])
    set_delay(sec)
    await event.reply(f"⏱ Delay set to {sec}s")


# -------------------- ADMINS --------------------

@bot.on(events.NewMessage(pattern="/addadmin"))
async def addadmin_cmd(event):
    uid = int(event.raw_text.split()[-1])
    add_admin(uid)
    await event.reply(f"✅ Admin {uid} added")


@bot.on(events.NewMessage(pattern="/removeadmin"))
async def removeadmin_cmd(event):
    uid = int(event.raw_text.split()[-1])
    remove_admin(uid)
    await event.reply(f"❌ Admin {uid} removed")


# -------------------- TARGETS --------------------

@bot.on(events.NewMessage(pattern="/addtarget"))
async def addtarget_cmd(event):
    tid = int(event.raw_text.split()[-1])
    add_target(tid)
    await event.reply(f"✅ Target {tid} added")


@bot.on(events.NewMessage(pattern="/removetarget"))
async def removetarget_cmd(event):
    tid = int(event.raw_text.split()[-1])
    remove_target(tid)
    await event.reply(f"❌ Target {tid} removed")


@bot.on(events.NewMessage(pattern="/listtargets"))
async def listtargets_cmd(event):
    targets = get_targets()
    await event.reply("\n".join(map(str, targets)))


# -------------------- COUNT --------------------

@bot.on(events.NewMessage(pattern="/count"))
async def count_cmd(event):
    await event.reply(f"📊 Total Forwarded: {get_count()}")


# -------------------- SKIP / RESUME --------------------

@bot.on(events.NewMessage(pattern="/skip"))
async def skip_cmd(event):
    global skip_next
    skip_next = True
    await event.reply("⏭ Next message skipped")


@bot.on(events.NewMessage(pattern="/resume"))
async def resume_cmd(event):
    global skip_next
    skip_next = False
    await event.reply("▶️ Resumed")


# -------------------- NOOR --------------------

@bot.on(events.NewMessage(pattern="/noor"))
async def noor_cmd(event):
    await event.reply(
        f"⚡ Status Report\nForwarding: {forwarding_on}\n"
        f"Targets: {len(get_targets())}\n"
        f"Delay: {get_delay()}s\n"
        f"Count: {get_count()}"
    )


# -------------------- FORWARDER --------------------

@user.on(events.NewMessage(incoming=True))
async def forwarder(event):
    global skip_next

    if not forwarding_on:
        return

    if skip_next:
        skip_next = False
        return

    for t in get_targets():
        try:
            await user.forward_messages(t, event.message)
            inc_count()
            await asyncio.sleep(get_delay())
        except:
            pass


# -------------------- MAIN --------------------

async def main():
    await bot.start()
    await user.start()
    print("✅ Bot Running")
    await asyncio.gather(
        bot.run_until_disconnected(),
        user.run_until_disconnected()
    )

asyncio.run(main())
