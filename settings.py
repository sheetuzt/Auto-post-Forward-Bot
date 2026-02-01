import os
import sys
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telethon import events

from angel_db import settings_col, admin_col, extra_targets_col

load_dotenv()

DEFAULT_ADMINS = [int(x) for x in os.getenv("DEFAULT_ADMINS", "").split(",") if x.strip()]

def is_admin(user_id):
    return user_id in DEFAULT_ADMINS or admin_col.find_one({"user_id": user_id})

async def get_all_target_channels():
    return [doc["chat_id"] for doc in extra_targets_col.find()]

async def add_target_channel(chat_id):
    extra_targets_col.update_one({"chat_id": chat_id}, {"$set": {"chat_id": chat_id}}, upsert=True)

async def remove_target_channel(chat_id):
    extra_targets_col.delete_one({"chat_id": chat_id})

def setup_extra_handlers(client):

    @client.on(events.NewMessage(pattern=r'^/setdelay (\d+)$'))
    async def set_delay(event):
        seconds = int(event.pattern_match.group(1))
        settings_col.update_one({"key": "delay"}, {"$set": {"value": seconds}}, upsert=True)
        client.delay_seconds = seconds
        await event.reply(f"⏱ Delay set: {seconds}s")

    @client.on(events.NewMessage(pattern=r'^/skip$'))
    async def skip_msg(event):
        settings_col.update_one({"key": "skip_next"}, {"$set": {"value": True}}, upsert=True)
        client.skip_next_message = True
        await event.reply("⏭ Next message skipped")

    @client.on(events.NewMessage(pattern=r'^/resume$'))
    async def resume(event):
        settings_col.update_one({"key": "skip_next"}, {"$set": {"value": False}}, upsert=True)
        client.skip_next_message = False
        await event.reply("▶ Forwarding resumed")

    @client.on(events.NewMessage(pattern=r'^/restart$'))
    async def restart_bot(event):
        await event.reply("♻ Restarting...")
        await asyncio.sleep(2)
        sys.exit(0)

async def load_initial_settings(client):
    delay = settings_col.find_one({"key": "delay"})
    client.delay_seconds = delay["value"] if delay else 5

    skip = settings_col.find_one({"key": "skip_next"})
    client.skip_next_message = skip["value"] if skip else False
