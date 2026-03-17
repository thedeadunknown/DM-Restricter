import os
import sqlite3
import threading
import logging
import asyncio
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("GatekeeperBot")

app = Flask(__name__)
@app.route('/')
def home(): return "NoDMBot is ACTIVE 🛡️"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

API_ID = int(os.getenv('API_ID', 0))
API_HASH = os.getenv('API_HASH', '')
STRING_SESSION = os.getenv('STRING_SESSION', '')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
LOG_GROUP_ID = int(os.getenv('LOG_GROUP_ID', 0))

active_requests = {}
DB_FILE = "whitelist.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS whitelist (user_id INTEGER PRIMARY KEY)")
    conn.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (ADMIN_ID,))
    conn.commit()
    conn.close()

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

@client.on(events.NewMessage(incoming=True))
async def gatekeeper(event):
    if event.is_private:
        sender = await event.get_sender()
        sender_id = event.sender_id
        
        if sender_id == ADMIN_ID or (sender and sender.bot): return

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM whitelist WHERE user_id = ?", (sender_id,))
        safe = cur.fetchone()
        conn.close()

        if not safe:
            new_msg_text = event.text
            await event.delete()
            
            if LOG_GROUP_ID != 0:
                if sender_id in active_requests:
                    try:
                        msg_id, old_text = active_requests[sender_id]
                        updated_text = old_text.replace("--- **Control Actions** ---", f"💬 **Update:** {new_msg_text}\n\n--- **Control Actions** ---")
                        
                        await client.edit_message(LOG_GROUP_ID, msg_id, updated_text)
                        active_requests[sender_id] = (msg_id, updated_text)
                        return
                    except Exception as e:
                        logger.error(f"Error editing message: {e}")

                info = (
                    f"📩 **New Message Request:**\n\n"
                    f"👤 **Name:** {sender.first_name if sender else 'Hidden'} {sender.last_name if sender and sender.last_name else ''}\n"
                    f"🆔 **ID:** `{sender_id}`\n\n"
                    f"💬 **Message:** {new_msg_text}\n\n"
                    f"--- **Control Actions** ---\n"
                    f"✅ Allow: `.ok {sender_id}`\n"
                    f"❌ Ignore: `.no {sender_id}`"
                )
                sent_msg = await client.send_message(LOG_GROUP_ID, info)
                active_requests[sender_id] = (sent_msg.id, info)

@client.on(events.NewMessage(pattern=r'\.(ok|no|rem) (\d+)'))
async def admin_action(event):
    if event.sender_id != ADMIN_ID: return
    
    action = event.pattern_match.group(1)
    target_id = int(event.pattern_match.group(2))

    conn = sqlite3.connect(DB_FILE)
    if action == "ok":
        conn.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (target_id,))
        conn.commit()
        if target_id in active_requests: del active_requests[target_id]
        await event.respond(f"✅ {target_id} added to whitelist.")
    
    elif action == "rem":
        conn.execute("DELETE FROM whitelist WHERE user_id = ?", (target_id,))
        conn.commit()
        await event.respond(f"🚫 {target_id} removed from whitelist.")
            
    else:
        if target_id in active_requests: del active_requests[target_id]
        await event.respond(f"🗑️ Request from {target_id} ignored.")
    
    conn.close()

@client.on(events.NewMessage(pattern=r'\.status', outgoing=True))
async def status(event):
    await event.edit("🛡️ Gatekeeper: ACTIVE\nFeature: Message Appending")

async def start_bot():
    init_db()
    logger.info("🚀 Starting Gatekeeper Service...")
    await client.start()
    await client.run_until_disconnected()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(start_bot())
