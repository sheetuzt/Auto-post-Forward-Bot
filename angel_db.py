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
settings_col = db["settings"]
count_col = db["count"]
sessions_col = db["sessions"]
history_col = db["history"]
admins_col = db["admins"]

# --- ADMINS ---
def get_admins_db():
    return [x["admin_id"] for x in admins_col.find()]

def add_admin_db(uid):
    admins_col.update_one({"admin_id": uid}, {"$set": {"admin_id": uid}}, upsert=True)

def remove_admin_db(uid):
    admins_col.delete_one({"admin_id": uid})

# --- SESSIONS (User Specific) ---
def save_session(owner_id, session_str):
    sessions_col.update_one(
        {"owner_id": owner_id}, 
        {"$set": {"data": session_str, "owner_id": owner_id}}, 
        upsert=True
    )

def load_session(owner_id):
    res = sessions_col.find_one({"owner_id": owner_id})
    return res["data"] if res else None

def get_last_active_session():
    # Returns the most recently updated session
    res = sessions_col.find_one(sort=[("_id", -1)])
    return res if res else None

def delete_session_db(owner_id):
    sessions_col.delete_one({"owner_id": owner_id})

# --- TARGETS & SOURCES (User Specific) ---
def get_targets(owner_id):
    return [x["target_id"] for x in targets_col.find({"owner_id": owner_id})]

def add_target(owner_id, tid):
    targets_col.update_one(
        {"target_id": tid, "owner_id": owner_id}, 
        {"$set": {"target_id": tid, "owner_id": owner_id}}, 
        upsert=True
    )

def remove_target(owner_id, tid):
    targets_col.delete_one({"target_id": tid, "owner_id": owner_id})

def get_sources(owner_id):
    return [x["source_id"] for x in sources_col.find({"owner_id": owner_id})]

def add_source_db(owner_id, sid):
    sources_col.update_one(
        {"source_id": sid, "owner_id": owner_id}, 
        {"$set": {"source_id": sid, "owner_id": owner_id}}, 
        upsert=True
    )

def remove_source_db(owner_id, sid):
    sources_col.delete_one({"source_id": sid, "owner_id": owner_id})

# --- SETTINGS (Delay per user) ---
def get_delay(owner_id):
    s = settings_col.find_one({"owner_id": owner_id})
    return int(s["value"]) if s else 5

def set_delay_db(owner_id, sec):
    settings_col.update_one(
        {"owner_id": owner_id}, 
        {"$set": {"value": int(sec), "owner_id": owner_id}}, 
        upsert=True
    )

# --- STATS ---
def inc_count(owner_id):
    count_col.update_one(
        {"owner_id": owner_id}, 
        {"$inc": {"value": 1}}, 
        upsert=True
    )

def get_count(owner_id):
    c = count_col.find_one({"owner_id": owner_id})
    return c["value"] if c else 0

def is_forwarded(msg_id, target_id):
    return history_col.find_one({"msg_id": msg_id, "target_id": target_id}) is not None

def mark_forwarded(msg_id, target_id):
    history_col.insert_one({"msg_id": msg_id, "target_id": target_id})
