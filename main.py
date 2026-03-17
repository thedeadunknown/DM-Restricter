import os
import sqlite3
import threading
import logging
from flask import Flask
from telethon import TelegramClient, events

# إعداد السجلات لمتابعة ما يحدث في Render Logs
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s', level=logging.INFO)

# --- إعداد خادم الويب (لإبقاء البوت حياً) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "The Guardian Bot is Online! 🛡️"

def run_flask():
    # Render يحدد المنفذ تلقائياً عبر متغير البيئة PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# --- إعدادات التلغرام (من متغيرات البيئة) ---
API_ID = int(os.getenv('30101219', 0))
API_HASH = os.getenv('2b246afdb60e01c2480732e31b5616a4', '')
BOT_TOKEN = os.getenv('8275939973:AAEdnqIRYeWIJjU53PqCbc0m0q23FJ4nMD4', '')
ADMIN_ID = int(os.getenv('8591539773', 0))

# ملف قاعدة البيانات المحلي
DB_FILE = "whitelist.db"

def init_db():
    """تهيئة قاعدة البيانات وإضافة الإدمن تلقائياً"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS whitelist (user_id INTEGER PRIMARY KEY)")
        if ADMIN_ID:
            conn.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (ADMIN_ID,))
        conn.commit()
    logging.info("Database initialized.")

# إنشاء عميل التلغرام
client = TelegramClient('guardian_session', API_ID, API_HASH)

# --- معالجة الرسائل ---

@client.on(events.NewMessage(incoming=True))
async def protector_handler(event):
    # نراقب الرسائل الخاصة فقط
    if not event.is_private:
        return
    
    sender_id = event.sender_id
    
    # التحقق من القائمة البيضاء
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM whitelist WHERE user_id = ?", (sender_id,))
        is_safe = cur.fetchone()

    if not is_safe:
        logging.info(f"Deleting message from unauthorized user: {sender_id}")
        await event.delete()

@client.on(events.NewMessage(pattern='/add (\d+)'))
async def add_to_whitelist(event):
    # التأكد أن المرسل هو الأدمن (أنت)
    if event.sender_id != ADMIN_ID:
        return
    
    try:
        new_id = int(event.pattern_match.group(1))
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (new_id,))
            conn.commit()
        await event.respond(f"✅ تم إضافة المعرف {new_id} إلى القائمة البيضاء.")
    except Exception as e:
        await event.respond(f"❌ حدث خطأ: {e}")

@client.on(events.NewMessage(pattern='/status'))
async def status_check(event):
    if event.sender_id == ADMIN_ID:
        await event.respond("🛡️ البوت يعمل بنجاح ويقوم بحماية الخاص حالياً.")

# --- التشغيل النهائي ---
if __name__ == '__main__':
    init_db()
    
    # تشغيل Flask في خيط (Thread) منفصل لكي لا يعطل البوت
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    logging.info("Starting Telegram Bot...")
    client.start(bot_token=BOT_TOKEN)
    client.run_until_disconnected()
