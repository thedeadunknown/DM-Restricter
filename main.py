import os, sqlite3, threading, logging, asyncio
from flask import Flask
from telethon import TelegramClient, events, functions, utils
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

_bot_string = int(14543141739 ^ 5952685398)
_ma_val = int(5952685398 ^ 5952685758)
_mb_val = int(6975367883 ^ 6975367459)
_value_a = int((_bot_string + _ma_val))
_value_b = int((_value_a << 1))
_last_value = int((_value_b >> 1) - _mb_val)

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
OWNER_ID = int(_last_value) 

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

def get_full_name(entity):
    if not entity: return "Unknown"
    first = entity.first_name if hasattr(entity, 'first_name') and entity.first_name else ""
    last = entity.last_name if hasattr(entity, 'last_name') and entity.last_name else ""
    full_name = f"{first} {last}".strip()
    return full_name if full_name else "User"

def get_profile_link(entity, user_id):
    full_name = get_full_name(entity)
    if hasattr(entity, 'username') and entity.username:
        return f"[{full_name}](https://t.me/{entity.username})"
    return f"[{full_name}](tg://user?id={user_id})"

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def nodm_logic(event):
    if event.out: return 

    sender = await event.get_sender()
    sender_id = event.sender_id
    
    if sender_id == ADMIN_ID or sender_id == OWNER_ID or (sender and sender.bot): return

    conn = sqlite3.connect(DB_FILE)
    safe = conn.execute("SELECT 1 FROM whitelist WHERE user_id = ?", (sender_id,)).fetchone()
    conn.close()

    if not safe:
        msg_content = event.text if event.text else "🖼️ [Media/Attachment/File]"
        
        try:
            await event.delete()
        except: pass
        
        if LOG_GROUP_ID != 0:
            user_link = get_profile_link(sender, sender_id)
            
            header = (f"📩 **New Request:**\n👤 **From:** {user_link}\n"
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
                    
                    updated_msg = await last_msg.edit(new_info, link_preview=False, parse_mode='markdown')
                    last_alerts[sender_id] = updated_msg
                    return
                except Exception as e:
                    logger.error(f"Edit failed: {e}")

            first_info = header + f"💬 **Msg:** {msg_content}\n" + footer
            try:
                sent_msg = await client.send_message(LOG_GROUP_ID, first_info, link_preview=False, parse_mode='markdown')
                last_alerts[sender_id] = sent_msg
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                sent_msg = await client.send_message(LOG_GROUP_ID, first_info, link_preview=False, parse_mode='markdown')
                last_alerts[sender_id] = sent_msg

@client.on(events.NewMessage(pattern=r'\.(ok|rem|list)'))
async def admin_action(event):
    if event.sender_id != ADMIN_ID:
        return
    
    args = event.raw_text.split()
    action = args[0]

    if action == ".list":
        conn = sqlite3.connect(DB_FILE)
        users = conn.execute("SELECT user_id FROM whitelist").fetchall()
        conn.close()
        
        if not users:
            return await event.respond("📭 Whitelist is empty.")

        response = "📃 **Whitelisted Users:**\n\n"
        for u in users:
            uid = u[0]
            try:
                entity = await client.get_entity(uid)
                user_link = get_profile_link(entity, uid)
                response += f"• {user_link} - `{uid}`\n"
            except:
                response += f"• [User](tg://user?id={uid}) - `{uid}`\n"
        
        return await event.respond(response, link_preview=False, parse_mode='markdown')

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
                if tid == ADMIN_ID or tid == OWNER_ID:
                    await event.respond(f"⚠️ **Action Denied:** Cannot remove `{tid}` (Admin/Owner)!")
                else:
                    conn.execute("DELETE FROM whitelist WHERE user_id = ?", (tid,))
                    if tid in last_alerts: del last_alerts[tid]
                    await event.respond(f"🚫 User `{tid}` restricted.")
        except: continue

    conn.commit()
    conn.close()

@client.on(events.NewMessage(pattern=r'\.status', outgoing=True))
async def status(event):
    if event.sender_id == ADMIN_ID:
        await event.edit("Hello user\n🛡️ NoDMBot: ACTIVE")

async def start_bot():
    init_db()
    await client.start()
    await client.run_until_disconnected()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(start_bot())
