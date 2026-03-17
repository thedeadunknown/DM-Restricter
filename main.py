import os
import sqlite3
import threading
import logging
import asyncio
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# إعداد السجلات لمراقبة البوت في Render
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("GuardianBot")

# --- 1. خادم الويب (لإبقاء البوت حياً) ---
app = Flask(__name__)
@app.route('/')
def home(): return "UserBot Shield is ACTIVE 🛡️"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# --- 2. الإعدادات والبيانات ---
API_ID = 30101219
API_HASH = '2b246afdb60e01c2480732e31b5616a4'
STRING_SESSION = os.getenv('STRING_SESSION')
ADMIN_ID = 8591539773 

DB_FILE = "whitelist.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS whitelist (user_id INTEGER PRIMARY KEY)")
    conn.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (ADMIN_ID,))
    conn.commit()
    conn.close()

# --- 3. تشغيل العميل (UserBot) ---
if not STRING_SESSION:
    logger.error("❌ STRING_SESSION missing in Environment Variables!")
    exit(1)

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

# --- 4. معالجة الرسائل الواردة (الحماية) ---
@client.on(events.NewMessage(incoming=True))
async def protector(event):
    if event.is_private:
        sender_id = event.sender_id
        
        # استثناء الأدمن (أنت) والرسائل المحفوظة
        if sender_id == ADMIN_ID:
            return

        # فحص قاعدة البيانات
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM whitelist WHERE user_id = ?", (sender_id,))
        safe = cur.fetchone()
        conn.close()

        if not safe:
            logger.info(f"🛡️ حظر: حذف رسالة من شخص غريب (ID: {sender_id})")
            await event.delete()

# --- 5. أوامر التحكم (تنفذها أنت فقط) ---
@client.on(events.NewMessage(pattern=r'\.add (\d+)'))
async def add_to_list(event):
    if event.out: # يعمل فقط عندما تكتب أنت الأمر
        try:
            target_id = int(event.pattern_match.group(1))
            conn = sqlite3.connect(DB_FILE)
            conn.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (target_id,))
            conn.commit()
            conn.close()
            await event.edit(f"✅ تم السماح للمعرف {target_id} بمراسلتك.")
        except:
            await event.edit("❌ خطأ: يرجى كتابة الرقم بشكل صحيح.")

@client.on(events.NewMessage(pattern=r'\.status'))
async def status(event):
    if event.out:
        await event.edit("🛡️ الحارس الشخصي يعمل الآن بنجاح على منصة Render.")

# --- 6. التشغيل النهائي ---
if __name__ == '__main__':
    init_db()
    # تشغيل Flask في خيط منفصل
    threading.Thread(target=run_flask, daemon=True).start()
    
    logger.info("🚀 Starting Guarding Service...")
    client.start()
    client.run_until_disconnected()
