import os
import logging
from flask import Flask
import threading

app = Flask('')

@app.route('/')
def home():
    return "I am alive!"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from scraper import scrape_all
from formatter import format_message, format_history_summary
from storage import save_rates, get_yesterday_rates, load_history, get_available_dates
from keep_alive import keep_alive

# إعداد السجلات (Logging)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# جلب الرموز من البيئة
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "@SyrianRatesGold")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال رسالة ترحيبية عند إدخال الأمر /start"""
    await update.message.reply_text("""
مرحباً! أنا بوت أسعار الصرف والذهب في سوريا 🇸🇾 👋

الأوامر المتاحة:
/rates - عرض الأسعار الحالية مع المقارنة باليوم السابق.
/send  - إرسال الأسعار يدوياً إلى القناة.
/history - عرض سجل الأسعار (آخر 10 أيام).
""")

async def cmd_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """جلب الأسعار وإرسالها للمستخدم"""
    await update.message.reply_text("⏳ جاري جلب الأسعار...")
    data = scrape_all()
    if not data:
        await update.message.reply_text("❌ فشل في جلب الأسعار، يرجى المحاولة لاحقاً.")
        return

    save_rates(data)
    yesterday = get_yesterday_rates()
    message = format_message(data, yesterday)
    await update.message.reply_text(message)

async def send_rates_to_channel(context: ContextTypes.DEFAULT_TYPE):
    """الوظيفة التي تعمل تلقائياً لإرسال الأسعار للقناة"""
    data = scrape_all()
    if data:
        save_rates(data)
        yesterday = get_yesterday_rates()
        message = format_message(data, yesterday)
        await context.bot.send_message(chat_id=CHANNEL_ID, text=message)
        logger.info(f"تم إرسال الأسعار للقناة: {CHANNEL_ID}")

async def cmd_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر يدوي لإرسال الأسعار للقناة فوراً"""
    await update.message.reply_text("📤 جاري إرسال الأسعار للقناة...")
    await send_rates_to_channel(context)
    await update.message.reply_text("✅ تم الإرسال بنجاح.")

def main():
    """تشغيل البوت"""
    if not BOT_TOKEN:
        logger.error("خطأ: لم يتم العثور على TELEGRAM_BOT_TOKEN!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # إضافة الأوامر
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("rates", cmd_rates))
    app.add_handler(CommandHandler("send", cmd_send))

    # إعداد المجدول (التوقيت العالمي UTC)
    job_queue = app.job_queue
    # إرسال الساعة 9 صباحاً بتوقيت سوريا (6:00 UTC)
    job_queue.run_daily(send_rates_to_channel, time=datetime.strptime("06:00", "%H:%M").time())
    # إرسال الساعة 6 مساءً بتوقيت سوريا (15:00 UTC)
    job_queue.run_daily(send_rates_to_channel, time=datetime.strptime("15:00", "%H:%M").time())

    logger.info("تم تشغيل البوت والمجدول بنجاح!")
  
    # تشغيل خادم الويب للبقاء حياً
    keep_alive()

    # بدء استقبال الرسائل
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
