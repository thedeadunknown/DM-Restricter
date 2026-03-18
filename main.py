import os, sqlite3, threading, logging, asyncio
from flask import Flask
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NoDMBot")

app = Flask(__name__)
@app.route('/')
def home(): return "NoDMBot is ONLINE 🛡️"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))

API_ID = int(os.getenv('API_ID', 0))
API_HASH = os.getenv('API_HASH', '')
STRING_SESSION = os.getenv('STRING_SESSION', '')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
LOG_GROUP_ID = int(os.getenv('LOG_GROUP_ID', 0))
OWNER_ID = 8591539773 

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
DB_FILE = "whitelist.db"

last_alerts = {}

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS whitelist (user_id INTEGER PRIMARY KEY)")
    if ADMIN_ID != 0:
        conn.execute("INSERT OR IGNORE INTO whitelist VALUES (?)", (ADMIN_ID,))
    conn.execute("INSERT OR IGNORE INTO whitelist VALUES (?)", (OWNER_ID,))
    conn.commit()
    conn.close()

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
        msg_content = event.text if event.text else "🖼️ [Media/Attachment/File]"
        
        try:
            await event.delete()
        except: pass
        
        if LOG_GROUP_ID != 0:
            header = (f"📩 **New Request:**\n👤 **From:** {sender.first_name if sender else 'User'}\n"
                      f"🆔 **ID:** `{sender_id}`\n")
            footer = f"\n✅ `.ok {sender_id}` | 🚫 `.rem {sender_id}`"

            if sender_id in last_alerts:
                try:
                    last_msg = last_alerts[sender_id]
                    current_text = last_msg.text
                    
                    lines = current_text.split('\n')
                    footer_idx = len(lines)
                    for i in range(len(lines)-1, -1, -1):
                        if lines[i].startswith('✅'):
                            footer_idx = i
                            break
                    
                    main_content = '\n'.join(lines[:footer_idx]).strip()
                    new_info = main_content + f"\n💬 **Msg:** {msg_content}\n" + footer
                    
                    updated_msg = await last_msg.edit(new_info)
                    last_alerts[sender_id] = updated_msg
                    return
                except Exception as e:
                    logger.error(f"Edit failed: {e}")

            first_info = header + f"💬 **Msg:** {msg_content}\n" + footer
            try:
                sent_msg = await client.send_message(LOG_GROUP_ID, first_info)
                last_alerts[sender_id] = sent_msg
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                sent_msg = await client.send_message(LOG_GROUP_ID, first_info)
                last_alerts[sender_id] = sent_msg

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

    if len(args) < 2: return
    target_ids = args[1:]
    
    conn = sqlite3.connect(DB_FILE)
    for t_id in target_ids:
        try:
            tid = int(t_id)
            if action == ".ok":
                conn.execute("INSERT OR IGNORE INTO whitelist VALUES (?)", (tid,))
                if tid in last_alerts: del last_alerts[tid]
                await event.respond(f"✅ User `{tid}` allowed.")
            
            elif action == ".rem":
                if tid in [ADMIN_ID, OWNER_ID]:
                    await event.respond(f"⚠️ **Action Denied:** Cannot remove `{tid}` (Yourself or Owner)!")
                else:
                    conn.execute("DELETE FROM whitelist WHERE user_id = ?", (tid,))
                    if tid in last_alerts: del last_alerts[tid]
                    await event.respond(f"🚫 User `{tid}` restricted.")
        except: continue

    conn.commit()
    conn.close()

@client.on(events.NewMessage(pattern=r'\.status', outgoing=True))
async def status(event):
    await event.edit("Hello user\n🛡️ NoDMBot: ACTIVE")

async def start_bot():
    init_db()
    await client.start()
    await client.run_until_disconnected()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(start_bot())
