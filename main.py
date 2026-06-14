"""
🎬 Telegram Episode Downloader Bot
Railway.app এ রান করার জন্য সম্পূর্ণ প্রস্তুত
"""

import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
import subprocess
from urllib.parse import urlparse

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
    """ইউজার ডাটাবেস লোড করুন"""
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_users_db(data):
    """ইউজার ডাটাবেস সেভ করুন"""
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"DB সেভ ত্রুটি: {e}")

def get_or_create_user(user_id, username, first_name):
    """ইউজার ডাটা পান অথবা তৈরি করুন"""
    db = load_users_db()
    user_id_str = str(user_id)
    
    if user_id_str not in db:
        db[user_id_str] = {
            'username': username or first_name,
            'first_name': first_name,
            'downloads': [],
            'playlist': [],
            'created_at': datetime.now().isoformat()
        }
        save_users_db(db)
    
    return db[user_id_str]

def add_download_record(user_id, title, link, status):
    """ডাউনলোড রেকর্ড যোগ করুন"""
    db = load_users_db()
    user_id_str = str(user_id)
    
    if user_id_str in db:
        db[user_id_str]['downloads'].append({
            'title': title,
            'link': link,
            'status': status,
            'timestamp': datetime.now().isoformat()
        })
        save_users_db(db)

def add_to_playlist(user_id, title, link):
    """প্লেলিস্টে যোগ করুন"""
    db = load_users_db()
    user_id_str = str(user_id)
    
    if user_id_str in db:
        if not any(p['link'] == link for p in db[user_id_str]['playlist']):
            db[user_id_str]['playlist'].append({
                'title': title,
                'link': link,
                'added_at': datetime.now().isoformat()
            })
            save_users_db(db)
            return True
    return False

def remove_from_playlist(user_id, index):
    """প্লেলিস্ট থেকে সরান"""
    db = load_users_db()
    user_id_str = str(user_id)
    
    if user_id_str in db and 0 <= index < len(db[user_id_str]['playlist']):
        removed = db[user_id_str]['playlist'].pop(index)
        save_users_db(db)
        return removed
    return None

def get_playlist(user_id):
    """প্লেলিস্ট পান"""
    db = load_users_db()
    user_id_str = str(user_id)
    
    if user_id_str in db:
        return db[user_id_str]['playlist']
    return []

# ========================
# DOWNLOAD FUNCTIONS
# ========================

def load_cookies():
    """Cookies লোড করুন"""
    try:
        with open(COOKIES_FILE, 'r') as f:
            return json.load(f)
    except:
        return None

def cookies_to_header(cookies):
    """Cookies কে header এ রূপান্তরিত করুন"""
    if not cookies:
        return ""
    cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
    return f"Cookie: {cookie_str}"

async def download_episode(url, title):
    """yt-dlp দিয়ে এপিসোড ডাউনলোড করুন (FFmpeg ফলব্যাক সহ)"""
    try:
        safe_title = title.replace('/', '-').replace('\\', '-').replace(':', '-')[:50]
        output_file = os.path.join(DOWNLOADS_DIR, f"{safe_title}.mp4")
        
        logger.info(f"📥 ডাউনলোড শুরু: {url}")
        
        # প্রথমে yt-dlp চেষ্টা করুন
        try:
            cmd = [
                'yt-dlp',
                '-f', 'best',
                '-o', output_file,
                '--quiet',
                '--progress',
                url
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.exists(output_file):
                file_size_mb = os.path.getsize(output_file) / 1024 / 1024
                logger.info(f"✅ yt-dlp দিয়ে ডাউনলোড সফল: {file_size_mb:.2f} MB")
                return {
                    'success': True,
                    'file': output_file,
                    'size_mb': file_size_mb
                }
            else:
                stderr_msg = stderr.decode()[:200] if stderr else "অজানা ত্রুটি"
                logger.warning(f"⚠️ yt-dlp ব্যর্থ: {stderr_msg}")
                # FFmpeg এ যান
                raise Exception("yt-dlp failed")
        
        except Exception as yt_dlp_error:
            logger.info("📥 FFmpeg ফলব্যাক চেষ্টা করছি...")
            
            # FFmpeg ফলব্যাক
            cookies = load_cookies()
            cookie_header = cookies_to_header(cookies)
            
            cmd = [
                'ffmpeg',
                '-allowed_extensions', 'ALL',
                '-i', url,
                '-c', 'copy',
                '-bsf:a', 'aac_adtstoasc',
                '-y',  # Overwrite output file
                output_file
            ]
            
            if cookie_header:
                cmd.insert(1, '-headers')
                cmd.insert(2, cookie_header)
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.exists(output_file):
                file_size_mb = os.path.getsize(output_file) / 1024 / 1024
                logger.info(f"✅ FFmpeg দিয়ে ডাউনলোড সফল: {file_size_mb:.2f} MB")
                return {
                    'success': True,
                    'file': output_file,
                    'size_mb': file_size_mb
                }
            else:
                error_msg = stderr.decode()[:200] if stderr else "অজানা ত্রুটি"
                logger.error(f"❌ FFmpeg ত্রুটি: {error_msg}")
                return {'success': False, 'error': 'ডাউনলোড ব্যর্থ - লিংক অনুপলব্ধ বা সুরক্ষিত'}
    
    except Exception as e:
        logger.error(f"❌ ডাউনলোড ত্রুটি: {e}")
        return {'success': False, 'error': f'ত্রুটি: {str(e)[:100]}'}

# ========================
# BOT COMMANDS
# ========================

class EpisodeDownloaderBot:
    def __init__(self):
        self.app = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """সব হ্যান্ডলার সেটআপ করুন"""
        self.app.add_handler(CommandHandler('start', self.start))
        self.app.add_handler(CommandHandler('help', self.help_cmd))
        self.app.add_handler(CommandHandler('history', self.history))
        self.app.add_handler(CommandHandler('playlist', self.show_playlist))
        self.app.add_handler(CommandHandler('add', self.add_playlist))
        self.app.add_handler(CommandHandler('remove', self.remove_playlist))
        self.app.add_handler(CommandHandler('stats', self.stats))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """স্টার্ট কমান্ড"""
        user = update.effective_user
        get_or_create_user(user.id, user.username, user.first_name)
        
        await update.message.reply_text(
            f"👋 স্বাগতম, <b>{user.first_name}</b>!\n\n"
            "🎬 আমি Episode ডাউনলোড করি।\n\n"
            "📖 <b>কমান্ড:</b>\n"
            "• শুধু লিংক পাঠান - ডাউনলোড করব\n"
            "/help - সাহায্য\n"
            "/playlist - প্লেলিস্ট দেখুন\n"
            "/history - ডাউনলোড হিস্টরি\n"
            "/stats - স্ট্যাটিস্টিক্স",
            parse_mode='HTML'
        )
    
    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """হেল্প কমান্ড"""
        await update.message.reply_text(
            "📖 <b>সাহায্য:</b>\n\n"
            "<b>ডাউনলোড করতে:</b>\n"
            "লিংক সহ মেসেজ পাঠান\n\n"
            "<b>প্লেলিস্ট:</b>\n"
            "/playlist - প্লেলিস্ট দেখুন\n"
            "/add [নাম] [লিংক] - যোগ করুন\n"
            "/remove [নম্বর] - সরান\n\n"
            "<b>অন্যান্য:</b>\n"
            "/history - হিস্টরি\n"
            "/stats - স্ট্যাটিস্টিক্স",
            parse_mode='HTML'
        )
    
    async def history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ডাউনলোড হিস্টরি"""
        user_id = str(update.effective_user.id)
        db = load_users_db()
        
        if user_id not in db or not db[user_id]['downloads']:
            await update.message.reply_text("📭 কোনো হিস্টরি নেই।")
            return
        
        downloads = db[user_id]['downloads'][-10:]
        text = "<b>📥 শেষ ১০টি ডাউনলোড:</b>\n\n"
        
        for i, dl in enumerate(downloads[::-1], 1):
            status = "✅" if dl['status'] == 'success' else "❌"
            text += f"{i}. {status} {dl['title']}\n"
        
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def show_playlist(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """প্লেলিস্ট দেখান"""
        user_id = update.effective_user.id
        playlist = get_playlist(user_id)
        
        if not playlist:
            await update.message.reply_text("📭 প্লেলিস্ট খালি।")
            return
        
        text = "<b>📋 আপনার প্লেলিস্ট:</b>\n\n"
        
        for i, item in enumerate(playlist, 1):
            text += f"{i}. <b>{item['title']}</b>\n"
        
        text += f"\n💡 /remove [নম্বর] দিয়ে সরান"
        
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def add_playlist(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """প্লেলিস্টে যোগ করুন"""
        if len(context.args) < 2:
            await update.message.reply_text("⚠️ ব্যবহার: /add [নাম] [লিংক]")
            return
        
        title = context.args[0]
        link = context.args[1]
        user_id = update.effective_user.id
        
        if add_to_playlist(user_id, title, link):
            await update.message.reply_text(f"✅ প্লেলিস্টে যোগ করা হয়েছে: {title}")
        else:
            await update.message.reply_text(f"⚠️ ইতিমধ্যে আছে: {title}")
    
    async def remove_playlist(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """প্লেলিস্ট থেকে সরান"""
        if not context.args:
            await update.message.reply_text("⚠️ ব্যবহার: /remove [নম্বর]")
            return
        
        try:
            index = int(context.args[0]) - 1
            user_id = update.effective_user.id
            
            removed = remove_from_playlist(user_id, index)
            if removed:
                await update.message.reply_text(f"✅ সরানো হয়েছে: {removed['title']}")
            else:
                await update.message.reply_text("❌ আইটেম পাওয়া যায়নি।")
        except:
            await update.message.reply_text("⚠️ সঠিক নম্বর দিন।")
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """স্ট্যাটিস্টিক্স"""
        user_id = str(update.effective_user.id)
        db = load_users_db()
        
        if user_id not in db:
            await update.message.reply_text("❌ কোনো ডাটা পাওয়া যায়নি।")
            return
        
        downloads = db[user_id]['downloads']
        playlist = db[user_id]['playlist']
        success = sum(1 for d in downloads if d['status'] == 'success')
        failed = sum(1 for d in downloads if d['status'] == 'failed')
        
        text = (
            f"📊 <b>আপনার স্ট্যাটিস্টিক্স:</b>\n\n"
            f"✅ সফল ডাউনলোড: <b>{success}</b>\n"
            f"❌ ব্যর্থ: <b>{failed}</b>\n"
            f"📥 মোট: <b>{len(downloads)}</b>\n"
            f"📋 প্লেলিস্ট: <b>{len(playlist)}</b>"
        )
        
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """লিংক সহ মেসেজ হ্যান্ডেল করুন"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        try:
            # লিংক খুঁজুন
            link = None
            for word in message_text.split():
                if word.startswith('http'):
                    link = word
                    break
            
            if not link:
                await update.message.reply_text("❌ কোনো লিংক পাওয়া যায়নি।")
                return
            
            # এপিসোড নাম খুঁজুন
            title = "Episode"
            if "নাম:" in message_text:
                for line in message_text.split('\n'):
                    if "নাম:" in line:
                        title = line.split(':', 1)[1].strip()
                        break
            
            # স্টেটাস মেসেজ
            status_msg = await update.message.reply_text(
                f"⏳ ডাউনলোড শুরু হচ্ছে...\n\n"
                f"📺 <b>{title}</b>\n"
                f"🔗 {link[:50]}...",
                parse_mode='HTML'
            )
            
            # ডাউনলোড করুন
            result = await download_episode(link, title)
            
            if result['success']:
                add_download_record(user_id, title, link, 'success')
                
                file_size = result['size_mb']
                
                if file_size > 100:
                    await status_msg.edit_text(
                        f"✅ <b>ডাউনলোড সফল!</b>\n\n"
                        f"📺 {title}\n"
                        f"📊 সাইজ: <b>{file_size:.2f} MB</b>\n"
                        f"⚠️ ফাইল বড় হওয়ায় সার্ভারে সংরক্ষিত।",
                        parse_mode='HTML'
                    )
                else:
                    # ছোট ফাইল পাঠান
                    try:
                        with open(result['file'], 'rb') as f:
                            await update.message.reply_video(
                                video=f,
                                caption=f"✅ {title}\n📊 {file_size:.2f} MB",
                            )
                    except Exception as e:
                        await status_msg.edit_text(
                            f"✅ <b>ডাউনলোড সফল!</b>\n\n"
                            f"📺 {title}\n"
                            f"📊 সাইজ: <b>{file_size:.2f} MB</b>\n"
                            f"⚠️ ফাইল পাঠাতে ত্রুটি: {str(e)[:50]}",
                            parse_mode='HTML'
                        )
            else:
                add_download_record(user_id, title, link, 'failed')
                await status_msg.edit_text(
                    f"❌ <b>ডাউনলোড ব্যর্থ</b>\n\n"
                    f"❌ {result['error']}",
                    parse_mode='HTML'
                )
        
        except Exception as e:
            logger.error(f"ত্রুটি: {e}")
            add_download_record(user_id, "Unknown", "", 'failed')
            await update.message.reply_text(f"❌ ত্রুটি: {str(e)[:100]}")
    
    def run(self):
        """বট চালু করুন"""
        logger.info("\n" + "="*60)
        logger.info("🎬 Episode Downloader Bot শুরু হয়েছে!")
        logger.info("="*60)
        logger.info(f"📥 ডাউনলোড ফোল্ডার: {DOWNLOADS_DIR}")
        logger.info("="*60 + "\n")
        self.app.run_polling()

if __name__ == '__main__':
    try:
        bot = EpisodeDownloaderBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("\n⛔ বট বন্ধ করা হয়েছে")
    except Exception as e:
        logger.error(f"❌ ত্রুটি: {e}")
