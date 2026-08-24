# Live Signal Scanner — One Link + Telegram

هذه النسخة مستقلة عن MT5 وVPS التداول. الهدف النهائي:
رابط واحد للموقع على الهاتف + بيانات XAU/USD وEUR/USD + إشعار Telegram عند ظهور BUY/SELL مع Entry/SL/TP.

## الخدمات المطلوبة
- Twelve Data API لمصدر بيانات السوق.
- Telegram Bot للإشعارات.
- استضافة Cloud لتشغيل Python 24/7 (مثل Render أو خدمة مشابهة). هذا ليس VPS تداولاً.

Twelve Data يوفر time series ببيانات Open/High/Low/Close وفواصل مثل 15min و1h و4h. 
Telegram Bot API يوفر sendMessage لإرسال الرسائل إلى chat_id.

## متغيرات البيئة
TWELVE_DATA_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

لا تضع هذه المفاتيح داخل HTML أو ترسلها في المحادثة.

## Render
الملف render.yaml موجود لتسهيل النشر:
- Runtime: Python
- Start command: gunicorn --chdir backend app:app
- Health endpoint: /api/health

بعد النشر، تحصل على رابط مثل:
https://اسم-الخدمة.onrender.com

ثم تفتح الرابط من الهاتف.

## إعداد Telegram
1. افتح Telegram وابحث عن @BotFather.
2. أنشئ Bot جديداً وخذ Bot Token.
3. أرسل رسالة إلى البوت من حسابك.
4. استخرج chat_id بالطريقة التي تختارها (يمكن استخدام getUpdates بعد إرسال رسالة).
5. ضع TOKEN وCHAT_ID كـ Environment Variables في منصة الاستضافة.

## منطق التنبيه
يُرسل تنبيه فقط عندما تتغير إشارة الأصل إلى BUY أو SELL على شمعة مغلقة جديدة.
لا يتم إرسال أوامر تداول.
