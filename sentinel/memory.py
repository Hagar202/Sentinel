"""Sentinel's memory: every result is saved in a small SQLite database."""
import json
import sqlite3
from datetime import datetime

from . import config


def connect():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS results (time TEXT, agent TEXT, verdict TEXT, sender TEXT, data TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS decisions (time TEXT, agent TEXT, action TEXT, decision TEXT)")
    return conn


def save(result, sender=""):
    conn = connect()
    conn.execute("INSERT INTO results VALUES (?, ?, ?, ?, ?)",
                 (result["time"], result["agent"], result["verdict"], sender, json.dumps(result, ensure_ascii=False)))
    conn.commit()
    conn.close()


def times_seen(sender):
    """How many times was this sender reported as phishing before?"""
    conn = connect()
    count = conn.execute("SELECT COUNT(*) FROM results WHERE sender = ? AND verdict = 'phishing'", (sender,)).fetchone()[0]
    conn.close()
    return count


def todays_results():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = connect()
    rows = conn.execute("SELECT data FROM results WHERE time LIKE ?", (today + "%",)).fetchall()
    conn.close()
    return [json.loads(row[0]) for row in rows]


def all_results():
    conn = connect()
    rows = conn.execute("SELECT data FROM results ORDER BY time DESC").fetchall()
    conn.close()
    return [json.loads(row[0]) for row in rows]


# ---------- Human decisions (approve / reject) ----------
def save_decision(agent, action, decision):
    conn = connect()
    conn.execute("INSERT INTO decisions VALUES (?, ?, ?, ?)",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), agent, action, decision))
    conn.commit()
    conn.close()


def decisions():
    conn = connect()
    rows = conn.execute("SELECT time, agent, action, decision FROM decisions ORDER BY time DESC").fetchall()
    conn.close()
    return [{"time": t, "agent": a, "action": ac, "decision": d} for t, a, ac, d in rows]
