import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["AutoForwardBot"]

# Collections
targets_col = db["targets"]
sources_col = db["sources"]
admins_col = db["admins"]
settings_col = db["settings"]
count_col = db["count"]
sessions_col = db["sessions"]
history_col = db["history"]

# --- AUTH & ADMINS ---
def is_admin_db(uid):
    return admins_col.find_one({"admin_id": uid}) is not None

def add_admin_db(uid):
    admins_col.update_one({"admin_id": uid}, {"$set": {"admin_id": uid}}, upsert=True)

def remove_admin_db(uid):
    admins_col.delete_one({"admin_id": uid})

# --- SESSION ---
def save_session(uid, session_str):
    sessions_col.update_one({"user_id": uid}, {"$set": {"data": session_str}}, upsert=True)

def load_session(uid):
    res = sessions_col.find_one({"user_id": uid})
    return res["data"] if res else None

def delete_session_db(uid):
    sessions_col.delete_one({"user_id": uid})

# --- TARGETS ---
def get_targets(uid):
    return [x["target_id"] for x in targets_col.find({"user_id": uid})]

def add_target(uid, tid):
    targets_col.update_one({"target_id": tid, "user_id": uid}, {"$set": {"target_id": tid, "user_id": uid}}, upsert=True)

def remove_target(uid, tid):
    targets_col.delete_one({"target_id": tid, "user_id": uid})

# --- SOURCES ---
def get_sources(uid):
    return [x["source_id"] for x in sources_col.find({"user_id": uid})]

def add_source_db(uid, sid):
    sources_col.update_one({"source_id": sid, "user_id": uid}, {"$set": {"source_id": sid, "user_id": uid}}, upsert=True)

def remove_source_db(uid, sid):
    sources_col.delete_one({"source_id": sid, "user_id": uid})

# --- SETTINGS ---
def get_delay(uid):
    s = settings_col.find_one({"key": "delay", "user_id": uid})
    return int(s["value"]) if s else 5

def set_delay_db(uid, sec):
    settings_col.update_one({"key": "delay", "user_id": uid}, {"$set": {"value": int(sec)}}, upsert=True)

def set_forwarding_db(uid, status):
    settings_col.update_one({"key": "forwarding", "user_id": uid}, {"$set": {"value": status}}, upsert=True)

def get_forwarding_db(uid):
    s = settings_col.find_one({"key": "forwarding", "user_id": uid})
    return s["value"] if s else False

# --- STATS ---
def inc_count(uid):
    count_col.update_one({"key": "total", "user_id": uid}, {"$inc": {"value": 1}}, upsert=True)

def get_count(uid):
    c = count_col.find_one({"key": "total", "user_id": uid})
    return c["value"] if c else 0

def is_forwarded(uid, msg_id, target_id):
    return history_col.find_one({"user_id": uid, "msg_id": msg_id, "target_id": target_id}) is not None

def mark_forwarded(uid, msg_id, target_id):
    history_col.insert_one({"user_id": uid, "msg_id": msg_id, "target_id": target_id})
