import sqlite3
from telethon import TelegramClient, events
import os

# بيانات التلغرام (يفضل وضعها في Environment Variables في Render)
api_id = int(os.getenv('API_ID', '0000000')) # استبدل بالأرقام الخاصة بك
api_hash = os.getenv('API_HASH', 'your_api_hash_here')
bot_token = os.getenv('BOT_TOKEN', 'your_bot_token_here')

# إعداد قاعدة البيانات لحفظ القائمة البيضاء
db_path = "whitelist.db"
conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
conn.commit()

client = TelegramClient('bot_session', api_id, api_hash).start(bot_token=bot_token)

# دالة للتحقق من وجود المستخدم في القائمة البيضاء
def is_whitelisted(user_id):
    cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone() is not None

@client.on(events.NewMessage(incoming=True))
async def protector_handler(event):
    if event.is_private:
        sender = await event.get_sender()
        sender_id = event.sender_id
        
        # إذا لم يكن في القائمة البيضاء
        if not is_whitelisted(sender_id):
            print(f"حذف رسالة من مستخدم غير مصرح به: {sender_id}")
            await event.delete()
            # يمكنك إرسال رسالة تحذيرية للمستخدم ثم حذفها لاحقاً إذا أردت

@client.on(events.NewMessage(pattern='/add (.+)'))
async def add_to_whitelist(event):
    # أمر لإضافة شخص (للمدير فقط)
    try:
        new_id = int(event.pattern_match.group(1))
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (new_id,))
        conn.commit()
        await event.respond(f"✅ تم إضافة المعرف {new_id} للقائمة البيضاء.")
    except Exception as e:
        await event.respond(f"❌ خطأ: تأكد من إرسال ID صحيح.")

@client.on(events.NewMessage(pattern='/list'))
async def show_list(event):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    if users:
        msg = "📋 القائمة البيضاء الحالية:\n" + "\n".join([str(u[0]) for u in users])
        await event.respond(msg)
    else:
        await event.respond("القائمة فارغة حالياً.")

print("الجهاز يعمل وحماية الخصوصية نشطة...")
client.run_until_disconnected()
