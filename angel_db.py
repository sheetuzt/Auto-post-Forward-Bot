import os
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI")
mongo = MongoClient(MONGO_URI)
db = mongo["forwardBot"]

targets_col = db["targets"]
admins_col = db["admins"]
settings_col = db["settings"]
count_col = db["count"]


# ---------------- TARGETS ----------------

def get_targets():
    return [x["target_id"] for x in targets_col.find()]

def add_target(tid):
    targets_col.update_one(
        {"target_id": tid},
        {"$set": {"target_id": tid}},
        upsert=True
    )

def remove_target(tid):
    targets_col.delete_one({"target_id": tid})


# ---------------- ADMINS ----------------

def get_admins():
    return [x["admin_id"] for x in admins_col.find()]

def add_admin(uid):
    admins_col.update_one(
        {"admin_id": uid},
        {"$set": {"admin_id": uid}},
        upsert=True
    )

def remove_admin(uid):
    admins_col.delete_one({"admin_id": uid})


# ---------------- DELAY ----------------

def get_delay():
    s = settings_col.find_one({"key": "delay"})
    return s["value"] if s else 2

def set_delay(sec):
    settings_col.update_one(
        {"key": "delay"},
        {"$set": {"value": sec}},
        upsert=True
    )


# ---------------- COUNT ----------------

def inc_count():
    count_col.update_one(
        {"key": "total"},
        {"$inc": {"value": 1}},
        upsert=True
    )

def get_count():
    c = count_col.find_one({"key": "total"})
    return c["value"] if c else 0
