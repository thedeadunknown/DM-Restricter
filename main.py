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

# جلب الإعدادات (تأكد أن الأسماء مطابقة تماماً لما في Render)
API_ID = int(os.getenv('API_ID', 0))
API_HASH = os.getenv('API_HASH', '')
STRING_SESSION = os.getenv('STRING_SESSION', '')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
LOG_GROUP_ID = int(os.getenv('LOG_GROUP_ID', 0))

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
DB_FILE = "whitelist.db"
active_requests = {}

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS whitelist (user_id INTEGER PRIMARY KEY)")
    if ADMIN_ID != 0:
        conn.execute("INSERT OR IGNORE INTO whitelist VALUES (?)", (ADMIN_ID,))
    conn.commit()
    conn.close()

# --- 1. الحماية (الرسائل الخاصة) ---
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def nodm_logic(event):
    # إذا الميساج خارج منك (أنت بعثته) -> لا تفعل شيئاً
    if event.out: return 

    sender = await event.get_sender()
    sender_id = event.sender_id
    
    # تجاهل الأدمن والبوتات
    if sender_id == ADMIN_ID or (sender and sender.bot): return

    conn = sqlite3.connect(DB_FILE)
    safe = conn.execute("SELECT 1 FROM whitelist WHERE user_id = ?", (sender_id,)).fetchone()
    conn.close()

    if not safe:
        msg_text = event.text if event.text else "🖼️ [Media/Attachment]"
        
        # حذف الرسالة مع معالجة الـ FloodWait
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

# --- 2. الأوامر (أوكي، ريم) ---
@client.on(events.NewMessage(pattern=r'\.(ok|rem) (\d+)'))
async def admin_action(event):
    # التأكد أنك أنت من أرسل الأمر
    if event.sender_id != ADMIN_ID: return
    
    cmd = event.raw_text.split()
    action, target_id = cmd[0], int(cmd[1])

    # حماية الأونر
    if action == ".rem" and target_id == ADMIN_ID:
        return await event.respond("⚠️ You can't remove yourself!")

    conn = sqlite3.connect(DB_FILE)
    if action == ".ok":
        conn.execute("INSERT OR IGNORE INTO whitelist VALUES (?)", (target_id,))
        await event.respond(f"✅ User `{target_id}` allowed.")
    elif action == ".rem":
        conn.execute("DELETE FROM whitelist WHERE user_id = ?", (target_id,))
        await event.respond(f"🚫 User `{target_id}` restricted.")
    conn.commit()
    conn.close()

# --- 3. أمر الحالة ---
@client.on(events.NewMessage(pattern=r'\.status', outgoing=True))
async def status(event):
    await event.edit("🛡️ NoDMBot: ACTIVE\nStatus: Protection & Anti-Flood ON")

async def start_bot():
    init_db()
    await client.start()
    print("🚀 Bot is connected and running!")
    await client.run_until_disconnected()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(start_bot())
