import os
import sys
import asyncio
from dotenv import load_dotenv
from telethon import events
from angel_db import settings_col, admin_col, extra_targets_col

load_dotenv()

DEFAULT_ADMINS = [int(x) for x in os.getenv("DEFAULT_ADMINS","").split(",") if x.strip()]

def is_admin(uid):
    return uid in DEFAULT_ADMINS or admin_col.find_one({"user_id": uid})

async def get_all_target_channels():
    return [x["chat_id"] for x in extra_targets_col.find()]

async def add_target_channel(cid):
    extra_targets_col.update_one({"chat_id": cid},{"$set":{"chat_id": cid}},upsert=True)

async def remove_target_channel(cid):
    extra_targets_col.delete_one({"chat_id": cid})

def setup_extra_handlers(client):

    @client.on(events.NewMessage(pattern=r'^/setdelay (\d+)$'))
    async def setdelay(e):
        sec = int(e.pattern_match.group(1))
        settings_col.update_one({"key":"delay"},{"$set":{"value":sec}},upsert=True)
        client.delay_seconds = sec
        await e.reply(f"⏱ Delay set {sec}s")

    @client.on(events.NewMessage(pattern=r'^/skip$'))
    async def skip(e):
        client.skip_next_message = True
        await e.reply("⏭ Next skipped")

    @client.on(events.NewMessage(pattern=r'^/resume$'))
    async def resume(e):
        client.skip_next_message = False
        await e.reply("▶ Resumed")

    @client.on(events.NewMessage(pattern=r'^/restart$'))
    async def restart(e):
        await e.reply("♻ Restarting")
        await asyncio.sleep(2)
        sys.exit(0)

async def load_initial_settings(client):
    d = settings_col.find_one({"key":"delay"})
    if d:
        client.delay_seconds = d["value"]
