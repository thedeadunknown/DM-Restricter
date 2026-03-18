import os, sqlite3, threading, logging, asyncio
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NoDMBot")

app = Flask(__name__)
@app.route('/')
def home(): return "NoDMBot is ONLINE 🛡️"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))

# --- CONFIGURATION ---
API_ID = int(os.getenv('API_ID', 0))
API_HASH = os.getenv('API_HASH', '')
STRING_SESSION = os.getenv('STRING_SESSION', '')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
LOG_GROUP_ID = int(os.getenv('LOG_GROUP_ID', 0))
OWNER_ID = 8591539773 

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
DB_FILE = "whitelist.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS whitelist (user_id INTEGER PRIMARY KEY)")
    if ADMIN_ID != 0:
        conn.execute("INSERT OR IGNORE INTO whitelist VALUES (?)", (ADMIN_ID,))
    conn.execute("INSERT OR IGNORE INTO whitelist VALUES (?)", (OWNER_ID,))
    conn.commit()
    conn.close()

# --- 1. Protection Logic ---
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def nodm_logic(event):
    if event.out: return 
    sender = await event.get_sender()
    sender_id = event.sender_id
    if sender_id in [ADMIN_ID, OWNER_ID] or (sender and sender.bot): return

    conn = sqlite3.connect(DB_FILE)
    safe = conn.execute("SELECT 1 FROM whitelist WHERE user_id = ?", (sender_id,)).fetchone()
    conn.close()

    if not safe:
        msg_text = event.text if event.text else "🖼️ [Media/Attachment]"
        try:
            await event.delete()
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            await event.delete()
        except: pass
        
        if LOG_GROUP_ID != 0:
            info = (f"📩 **New Request:**\n👤 **From:** {sender.first_name if sender else 'User'}\n"
                    f"🆔 **ID:** `{sender_id}`\n💬 **Msg:** {msg_text}\n\n"
                    f"✅ `.ok {sender_id}` | 🚫 `.rem {sender_id}`")
            try:
                await client.send_message(LOG_GROUP_ID, info)
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                await client.send_message(LOG_GROUP_ID, info)

# --- 2. Admin Actions (.ok, .rem, .list) ---
@client.on(events.NewMessage(pattern=r'\.(ok|rem|list)'))
async def admin_action(event):
    if event.sender_id not in [ADMIN_ID, OWNER_ID]: return
    
    args = event.raw_text.split()
    action = args[0]

    if action == ".list":
        conn = sqlite3.connect(DB_FILE)
        users = conn.execute("SELECT user_id FROM whitelist").fetchall()
        conn.close()
        msg = "📃 **Whitelisted Users:**\n\n" + "\n".join([f"• `{u[0]}`" for u in users]) if users else "📭 Whitelist is empty."
        return await event.respond(msg)

    # نظام الحذف أو الإضافة المتعددة
    if len(args) < 2: return
    target_ids = args[1:] # جلب كل الـ IDs المكتوبة بعد الأمر
    
    conn = sqlite3.connect(DB_FILE)
    success_count = 0
    errors = []

    for t_id in target_ids:
        try:
            tid = int(t_id)
            if action == ".rem":
                if tid in [ADMIN_ID, OWNER_ID]:
                    errors.append(f"`{tid}` (Protected)")
                    continue
                conn.execute("DELETE FROM whitelist WHERE user_id = ?", (tid,))
            elif action == ".ok":
                conn.execute("INSERT OR IGNORE INTO whitelist VALUES (?)", (tid,))
            success_count += 1
        except ValueError:
            errors.append(f"`{t_id}` (Invalid)")

    conn.commit()
    conn.close()

    # رد مجمع بالنتيجة
    status_msg = f"✅ Done! Processed **{success_count}** IDs."
    if errors:
        status_msg += f"\n⚠️ Skipped: {', '.join(errors)}"
    await event.respond(status_msg)

# --- 3. Status Command ---
@client.on(events.NewMessage(pattern=r'\.status', outgoing=True))
async def status(event):
    await event.edit("🛡️ NoDMBot: ACTIVE\nStatus: Multi-ID Support Enabled")

async def start_bot():
    init_db()
    await client.start()
    await client.run_until_disconnected()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(start_bot())
