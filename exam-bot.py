import telebot
import img2pdf
import os
import io
import requests
from PIL import Image
from flask import Flask
from threading import Thread
import time

# --- إعدادات البوت (سنضع القيم الحقيقية في إعدادات Render لاحقاً) ---
TOKEN = os.environ.get('8261684561:AAFxV6w5o0_jmWp80KrvUr_8u0mHWygFoxg')
WEBSITE_API_URL = os.environ.get('WEBSITE_API_URL')
API_SECRET = os.environ.get('https://script.google.com/macros/s/AKfycbwAChxiDyxCDCgw9GfQqrXyLy_4ZhYTQWKiwqMK8Yi8Kk1Oy93OhH0NiTT5DvF-Iyp7XA/exec')
# -----------------------------

bot = telebot.TeleBot(TOKEN)
user_data = {}
user_ids = {}

# --- سيرفر وهمي لإبقاء البوت يعمل على Render ---
app = Flask('')


@app.route('/')
def home():
    return "I am alive! The Bot is running."


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()


# ---------------------------------------------

def compress_image(file_bytes):
    img = Image.open(io.BytesIO(file_bytes)).convert('RGB')
    if img.width > 1500:
        ratio = 1500 / float(img.width)
        img = img.resize((1500, int(float(img.height) * float(ratio))), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=60, optimize=True)
    return output.getvalue()


@bot.message_handler(commands=['start'])
def send_welcome(message):
    args = message.text.split()
    if len(args) > 1:
        student_id_from_site = args[1]
        user_ids[message.chat.id] = student_id_from_site
        welcome_text = f"👋 أهلاً بك! تم ربط حسابك بالرقم: **{student_id_from_site}**\n📸 أرسل صور الامتحان الآن، ثم اضغط /done"
    else:
        welcome_text = "⚠️ يرجى الدخول للبوت عن طريق الرابط في الموقع."

    user_data[message.chat.id] = []
    bot.reply_to(message, welcome_text)


@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    chat_id = message.chat.id
    if chat_id not in user_ids:
        bot.reply_to(message, "⚠️ ادخل عبر رابط الموقع.")
        return

    if chat_id not in user_data: user_data[chat_id] = []

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        compressed = compress_image(downloaded)

        filename = f"{chat_id}_{len(user_data[chat_id])}.jpg"
        with open(filename, 'wb') as f:
            f.write(compressed)

        user_data[chat_id].append(filename)
        # لا نرسل رد لكل صورة لتجنب الازعاج والبطء، يمكن الاكتفاء برد نهائي
    except Exception as e:
        print(e)


@bot.message_handler(commands=['done'])
def upload_to_site(message):
    chat_id = message.chat.id
    if chat_id not in user_ids: return
    if not user_data.get(chat_id):
        bot.reply_to(message, "⚠️ لم ترسل صوراً!")
        return

    msg = bot.reply_to(message, "⏳ جاري المعالجة والرفع...")
    pdf_filename = f"Exam_{user_ids[chat_id]}.pdf"

    try:
        with open(pdf_filename, "wb") as f:
            f.write(img2pdf.convert(user_data[chat_id]))

        with open(pdf_filename, 'rb') as f:
            files = {'pdf_file': f}
            data = {'secret': API_SECRET, 'student_id': user_ids[chat_id]}
            response = requests.post(WEBSITE_API_URL, files=files, data=data)

            if response.text.strip() == "success":
                bot.edit_message_text(f"✅ **تم التسليم بنجاح!**", chat_id, msg.message_id)
            else:
                bot.edit_message_text(f"❌ خطأ من الموقع: {response.text}", chat_id, msg.message_id)

        for img in user_data[chat_id]:
            if os.path.exists(img): os.remove(img)
        if os.path.exists(pdf_filename): os.remove(pdf_filename)
        user_data[chat_id] = []

    except Exception as e:
        bot.reply_to(message, "حدث خطأ تقني.")
        print(e)


# تشغيل السيرفر الوهمي ثم البوت
keep_alive()
bot.infinity_polling()