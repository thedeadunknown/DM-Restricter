import os
import sqlite3
import threading
import logging
import asyncio
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("NoDMBot")

app = Flask(__name__)
@app.route('/')
def home(): return "NoDMBot is ACTIVE 🛡️"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# --- SECURE CONFIGURATION (Fetch from Render Environment Variables) ---
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
    if ADMIN_ID != 0:
        conn.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (ADMIN_ID,))
    conn.commit()
    conn.close()

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

# --- 1. Protection Logic (Private Messages) ---
@client.on(events.NewMessage(incoming=True))
async def nodm_logic(event):
    if event.is_private:
        sender = await event.get_sender()
        sender_id = event.sender_id
        
        # Ignore Admin and other bots
        if sender_id == ADMIN_ID or (sender and sender.bot): return

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM whitelist WHERE user_id = ?", (sender_id,))
        safe = cur.fetchone()
        conn.close()

        if not safe:
            new_msg_text = event.text
            await event.delete() # Instant delete from PM
            
            if LOG_GROUP_ID != 0:
                # If the user already has an active log entry, append the message
                if sender_id in active_requests:
                    try:
                        msg_id, old_text = active_requests[sender_id]
                        updated_text = old_text.replace("--- **Control Actions** ---", f"💬 **Update:** {new_msg_text}\n\n--- **Control Actions** ---")
                        
                        await client.edit_message(LOG_GROUP_ID, msg_id, updated_text)
                        active_requests[sender_id] = (msg_id, updated_text)
                        return
                    except Exception as e:
                        logger.error(f"Error editing message: {e}")

                # First time message from this user
                info = (
                    f"📩 **New Message Request (NoDMBot):**\n\n"
                    f"👤 **Name:** {sender.first_name if sender else 'Hidden'} {sender.last_name if sender and sender.last_name else ''}\n"
                    f"🆔 **ID:** `{sender_id}`\n\n"
                    f"💬 **Message:** {new_msg_text}\n\n"
                    f"--- **Control Actions** ---\n"
                    f"✅ Allow: `.ok {sender_id}`\n"
                    f"❌ Ignore: `.no {sender_id}`"
                )
                sent_msg = await client.send_message(LOG_GROUP_ID, info)
                active_requests[sender_id] = (sent_msg.id, info)

# --- 2. Admin Command Handling ---
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
        if target_id != ADMIN_ID:
            conn.execute("DELETE FROM whitelist WHERE user_id = ?", (target_id,))
            conn.commit()
            await event.respond(f"🚫 {target_id} removed from whitelist.")
            
    else: # "no" action
        if target_id in active_requests: del active_requests[target_id]
        await event.respond(f"🗑️ Request from {target_id} ignored.")
    
    conn.close()

# --- 3. Status Command ---
@client.on(events.NewMessage(pattern=r'\.status', outgoing=True))
async def status(event):
    await event.edit("🛡️ NoDMBot: ACTIVE\nStatus: Secure Mode (Hidden Env)")

async def start_bot():
    init_db()
    logger.info("🚀 Starting NoDMBot Service...")
    await client.start()
    await client.run_until_disconnected()

if __name__ == '__main__':
    # Start Web Server for Render Uptime
    threading.Thread(target=run_flask, daemon=True).start()
    # Run Telegram Client
    asyncio.run(start_bot())
