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

# قاموس لتخزين ID الرسالة التي أُرسلت لكل مستخدم في المجموعة
active_requests = {}

DB_FILE = "whitelist.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS whitelist (user_id INTEGER PRIMARY KEY)")
    conn.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (ADMIN_ID,))
    conn.commit()
    conn.close()

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

# --- 1. حماية الخاص مع نظام "تعديل الرسالة" ---
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
            await event.delete() # حذف من الخاص فوراً
            
            if LOG_GROUP_ID != 0:
                # إذا كان لهذا الشخص رسالة سابقة في المجموعة (لم نرد عليها بعد)
                if sender_id in active_requests:
                    try:
                        msg_id, old_text = active_requests[sender_id]
                        # نقوم بتحديث النص وإضافة الرسالة الجديدة
                        updated_text = old_text.replace("--- **إجراءات التحكم** ---", f"💬 **تكملة:** {new_msg_text}\n\n--- **إجراءات التحكم** ---")
                        
                        await client.edit_message(LOG_GROUP_ID, msg_id, updated_text)
                        # تحديث القاموس بالنص الجديد
                        active_requests[sender_id] = (msg_id, updated_text)
                        return
                    except Exception as e:
                        logger.error(f"Error editing message: {e}")

                # إذا كانت أول رسالة لهذا الشخص
                info = (
                    f"📩 **طلب مراسلة جديد:**\n\n"
                    f"👤 **الاسم:** {sender.first_name if sender else 'Hidden'} {sender.last_name if sender and sender.last_name else ''}\n"
                    f"🆔 **المعرف:** `{sender_id}`\n\n"
                    f"💬 **الرسالة:** {new_msg_text}\n\n"
                    f"--- **إجراءات التحكم** ---\n"
                    f"✅ للسماح: `.ok {sender_id}`\n"
                    f"❌ للرفض: `.no {sender_id}`"
                )
                sent_msg = await client.send_message(LOG_GROUP_ID, info)
                # حفظ ID الرسالة والنص الأصلي للرجوع إليهما
                active_requests[sender_id] = (sent_msg.id, info)

# --- 2. معالجة الأوامر ---
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
        await event.respond(f"✅ تم إضافة {target_id} للقائمة البيضاء.")
    
    elif action == "rem":
        conn.execute("DELETE FROM whitelist WHERE user_id = ?", (target_id,))
        conn.commit()
        await event.respond(f"🚫 تم حذف {target_id} من القائمة.")
            
    else: # no
        if target_id in active_requests: del active_requests[target_id]
        await event.respond(f"🗑️ تم تجاهل طلب {target_id}.")
    
    conn.close()

@client.on(events.NewMessage(pattern=r'\.status', outgoing=True))
async def status(event):
    await event.edit("🛡️ نظام الوسيط ACTIVE\nالميزة: تعديل الرسائل (Message Appending)")

async def start_bot():
    init_db()
    logger.info("🚀 Starting Gatekeeper Service with Edit Mode...")
    await client.start()
    await client.run_until_disconnected()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(start_bot())
