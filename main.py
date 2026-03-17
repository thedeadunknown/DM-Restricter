import os
import sqlite3
import threading
import logging
import asyncio
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# إعداد السجلات
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("GatekeeperBot")

app = Flask(__name__)
@app.route('/')
def home(): return "Gatekeeper is ACTIVE 🛡️"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# --- الإعدادات ---
API_ID = 30101219
API_HASH = '2b246afdb60e01c2480732e31b5616a4'
STRING_SESSION = os.getenv('STRING_SESSION')
ADMIN_ID = 8591539773 
LOG_GROUP_ID = int(os.getenv('LOG_GROUP_ID', 0)) 

DB_FILE = "whitelist.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS whitelist (user_id INTEGER PRIMARY KEY)")
    conn.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (ADMIN_ID,))
    conn.commit()
    conn.close()

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

# --- 1. حماية الخاص ونظام الوسيط ---
@client.on(events.NewMessage(incoming=True))
async def gatekeeper(event):
    if event.is_private:
        sender = await event.get_sender()
        sender_id = event.sender_id
        
        # تجاهل الرسائل من نفسك أو من البوتات
        if sender_id == ADMIN_ID or sender.bot: return

        # فحص القائمة البيضاء
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM whitelist WHERE user_id = ?", (sender_id,))
        safe = cur.fetchone()
        conn.close()

        if not safe:
            msg_text = event.text
            await event.delete() # حذف من الخاص فوراً
            
            if LOG_GROUP_ID != 0:
                # إنشاء رسالة تحتوي على أوامر قابلة للضغط (Hyperlinks)
                info = (
                    f"📩 **طلب مراسلة جديد:**\n\n"
                    f"👤 **الاسم:** {sender.first_name} {sender.last_name or ''}\n"
                    f"🆔 **المعرف:** `{sender_id}`\n"
                    f"🔗 **الحساب:** @{sender.username or 'None'}\n"
                    f"💬 **الرسالة:** {msg_text}\n\n"
                    f"--- **إجراءات التحكم** ---\n"
                    f"✅ للسماح: `.ok {sender_id}`\n"
                    f"❌ للرفض: `.no {sender_id}`"
                )
                await client.send_message(LOG_GROUP_ID, info)

# --- 2. معالجة الأوامر من مجموعة الوسيط ---
@client.on(events.NewMessage(pattern=r'\.(ok|no) (\d+)'))
async def admin_action(event):
    # التأكد أن الأمر جاء منك أنت وفي مجموعة الوسيط
    if event.sender_id != ADMIN_ID: return
    
    action = event.pattern_match.group(1)
    target_id = int(event.pattern_match.group(2))

    if action == "ok":
        conn = sqlite3.connect(DB_FILE)
        conn.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (target_id,))
        conn.commit()
        conn.close()
        await event.respond(f"✅ تم إضافة {target_id} للقائمة البيضاء بنجاح.")
    else:
        await event.respond(f"🗑️ تم تجاهل طلب المعرف {target_id}.")

# --- 3. الأوامر المعتادة ---
@client.on(events.NewMessage(pattern=r'\.status', outgoing=True))
async def status(event):
    await event.edit("🛡️ نظام الوسيط (النسخة النصية) يعمل بنجاح!")

async def start_bot():
    init_db()
    logger.info("🚀 Starting Gatekeeper Service...")
    await client.start()
    await client.run_until_disconnected()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(start_bot())
