import os
import sqlite3
import threading
import logging
import asyncio
from flask import Flask
from telethon import TelegramClient, events, Button
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

# ضع هنا ID المجموعة الخاصة (الوسيط) - سأعلمك كيف تجده
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
        
        if sender_id == ADMIN_ID or sender.bot: return

        # فحص القائمة البيضاء
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM whitelist WHERE user_id = ?", (sender_id,))
        safe = cur.fetchone()
        conn.close()

        if not safe:
            # 1. حذف الرسالة فوراً من الخاص
            msg_text = event.text
            await event.delete()
            
            # 2. إرسال "بطاقة تعريف" للمجموعة الوسيطة مع أزرار
            if LOG_GROUP_ID != 0:
                info = f"📩 **طلب مراسلة جديد:**\n"
                info += f"👤 **الاسم:** {sender.first_name} {sender.last_name or ''}\n"
                info += f"🆔 **المعرف:** `{sender_id}`\n"
                info += f"🔗 **الحساب:** @{sender.username or 'لا يوجد'}\n"
                info += f"💬 **الرسالة:** {msg_text}"
                
                buttons = [
                    [Button.inline("✅ قبول السماح", data=f"ok_{sender_id}"),
                     Button.inline("❌ حظر نهائي", data=f"no_{sender_id}")]
                ]
                await client.send_message(LOG_GROUP_ID, info, buttons=buttons)

# --- 2. معالجة ضغطات الأزرار (في المجموعة) ---
@client.on(events.CallbackQuery)
async def callback(event):
    data = event.data.decode('utf-8')
    admin_who_clicked = event.sender_id
    
    # التأكد أنك أنت فقط من يضغط الأزرار
    if admin_who_clicked != ADMIN_ID:
        await event.answer("⚠️ لست مخولاً بالتحكم!", alert=True)
        return

    if data.startswith("ok_"):
        user_id = int(data.split("_")[1])
        conn = sqlite3.connect(DB_FILE)
        conn.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()
        await event.edit(f"✅ تم القبول! المعرف {user_id} يمكنه مراسلتك الآن.")
        
    elif data.startswith("no_"):
        user_id = int(data.split("_")[1])
        # يمكنك إضافة كود للحظر النهائي هنا إذا أردت
        await event.edit(f"❌ تم الرفض وحذف الطلب (ID: {user_id}).")

# --- 3. الأوامر المعتادة ---
@client.on(events.NewMessage(pattern=r'\.status', outgoing=True))
async def status(event):
    await event.edit("🛡️ نظام الوسيط يعمل بنجاح!")

async def start_bot():
    init_db()
    logger.info("🚀 Starting Gatekeeper Service...")
    await client.start()
    await client.run_until_disconnected()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(start_bot())
