"""
🎬 Telegram Episode Downloader Bot
yt-dlp এবং Cookies ইন্টিগ্রেটেড সংস্করণ
"""

import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
import yt_dlp

# ========================
# SETUP
# ========================

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
DOWNLOADS_DIR = './downloads'
DB_FILE = 'users_data.json'
COOKIES_FILE = '.cookies.json'

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========================
# DATABASE FUNCTIONS
# ========================

def load_users_db():
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_users_db(data):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"DB সেভ ত্রুটি: {e}")

def add_download_record(user_id, title, link, status):
    db = load_users_db()
    user_id_str = str(user_id)
    if user_id_str not in db:
        db[user_id_str] = {'downloads': []}
    db[user_id_str]['downloads'].append({
        'title': title, 'link': link, 'status': status, 'timestamp': datetime.now().isoformat()
    })
    save_users_db(db)

# ========================
# DOWNLOAD FUNCTIONS
# ========================

async def download_episode(url, title):
    """yt-dlp ব্যবহার করে ডাউনলোড"""
    try:
        safe_title = title.replace('/', '-').replace('\\', '-')[:50]
        output_file = os.path.join(DOWNLOADS_DIR, f"{safe_title}.mp4")
        
        logger.info(f"📥 ডাউনলোড শুরু: {url}")
        
        # yt-dlp অপশন
        ydl_opts = {
            'format': 'best',
            'outtmpl': output_file,
            'cookiefile': COOKIES_FILE, # গিটহাবে থাকা কুকি ফাইল
            'quiet': False,
        }
        
        # ডাউনলোড প্রসেস
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        if os.path.exists(output_file):
            file_size_mb = os.path.getsize(output_file) / 1024 / 1024
            return {'success': True, 'file': output_file, 'size_mb': file_size_mb}
        else:
            return {'success': False, 'error': 'ফাইল তৈরি হয়নি'}
    
    except Exception as e:
        logger.error(f"ডাউনলোড ত্রুটি: {e}")
        return {'success': False, 'error': str(e)}

# ========================
# BOT CLASS
# ========================

class EpisodeDownloaderBot:
    def __init__(self):
        self.app = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        self.app.add_handler(CommandHandler('start', self.start))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("👋 স্বাগতম! ভিডিওর লিঙ্ক পাঠান, আমি ডাউনলোড করছি।")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        message_text = update.message.text
        
        link = None
        for word in message_text.split():
            if word.startswith('http'):
                link = word
                break
        
        if not link:
            await update.message.reply_text("❌ লিঙ্ক পাওয়া যায়নি।")
            return
            
        status_msg = await update.message.reply_text("⏳ ডাউনলোড শুরু হচ্ছে...")
        
        result = await download_episode(link, "Video_Download")
        
        if result['success']:
            add_download_record(user_id, "Video", link, 'success')
            with open(result['file'], 'rb') as f:
                await update.message.reply_video(video=f, caption=f"✅ সফল! সাইজ: {result['size_mb']:.2f} MB")
            os.remove(result['file'])
            await status_msg.delete()
        else:
            add_download_record(user_id, "Video", link, 'failed')
            await status_msg.edit_text(f"❌ ডাউনলোড ব্যর্থ: {result['error']}")

    def run(self):
        self.app.run_polling()

if __name__ == '__main__':
    bot = EpisodeDownloaderBot()
    bot.run()
