import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["AutoForwardBot"]

# Collections
targets_col = db["targets"]
sources_col = db["sources"] # New collection for sources
admins_col = db["admins"]
settings_col = db["settings"]
count_col = db["count"]
sessions_col = db["sessions"]
history_col = db["history"]

# --- SESSION ---
def save_session(session_str):
    sessions_col.update_one({"key": "user_session"}, {"$set": {"data": session_str}}, upsert=True)

def load_session():
    res = sessions_col.find_one({"key": "user_session"})
    return res["data"] if res else None

def delete_session_db():
    sessions_col.delete_one({"key": "user_session"})

# --- TARGETS ---
def get_targets():
    return [x["target_id"] for x in targets_col.find()]

def add_target(tid):
    targets_col.update_one({"target_id": tid}, {"$set": {"target_id": tid}}, upsert=True)

def remove_target(tid):
    targets_col.delete_one({"target_id": tid})

# --- SOURCES (New Functions) ---
def get_sources():
    return [x["source_id"] for x in sources_col.find()]

def add_source_db(sid):
    sources_col.update_one({"source_id": sid}, {"$set": {"source_id": sid}}, upsert=True)

def remove_source_db(sid):
    sources_col.delete_one({"source_id": sid})

# --- ADMINS ---
def get_admins_db():
    return [x["admin_id"] for x in admins_col.find()]

def add_admin_db(uid):
    admins_col.update_one({"admin_id": uid}, {"$set": {"admin_id": uid}}, upsert=True)

def remove_admin_db(uid):
    admins_col.delete_one({"admin_id": uid})

# --- SETTINGS ---
def get_delay():
    s = settings_col.find_one({"key": "delay"})
    return int(s["value"]) if s else 5

def set_delay_db(sec):
    settings_col.update_one({"key": "delay"}, {"$set": {"value": int(sec)}}, upsert=True)

# --- STATS ---
def inc_count():
    count_col.update_one({"key": "total"}, {"$inc": {"value": 1}}, upsert=True)

def get_count():
    c = count_col.find_one({"key": "total"})
    return c["value"] if c else 0

def is_forwarded(msg_id, target_id):
    return history_col.find_one({"msg_id": msg_id, "target_id": target_id}) is not None

def mark_forwarded(msg_id, target_id):
    history_col.insert_one({"msg_id": msg_id, "target_id": target_id})
