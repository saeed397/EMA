# 📈 Crypto Multi-Timeframe Confluence Scanner

اسکنر سیگنال کریپتو با امتیازدهی وزن‌دار ۰–۱۰۰ (۱۰ مؤلفه در ۴ بلوک)، فیلتر تایم‌فریم بالاتر و
مشتق‌گیری هموار با **فیلتر کالمن** (Local Linear Trend).

## اجرای محلی
```bash
pip install -r requirements.txt
streamlit run app.py
```

## ۱) ساخت مخزن GitHub و آپلود فایل‌ها
1. وارد github.com شوید → **New repository** → نام: `crypto-scanner` → Public → Create.
2. در صفحه مخزن: **Add file → Upload files** → همه فایل‌های این پوشه را بکشید و رها کنید →
   **Commit changes**.
   (یا با ترمینال:)
```bash
git init && git add . && git commit -m "init"
git branch -M main
git remote add origin https://github.com/<USERNAME>/crypto-scanner.git
git push -u origin main
```

## ۲) اتصال Streamlit Cloud به مخزن
1. به https://share.streamlit.io بروید و با GitHub وارد شوید.
2. **Create app → Deploy a public app from GitHub**.
3. Repository: `<USERNAME>/crypto-scanner` — Branch: `main` — Main file path: `app.py`.
4. **Deploy**. آدرسی مثل `https://<app-name>.streamlit.app` می‌گیرید.

## ۳) ساخت آیکون میانبر روی صفحه گوشی (اجرا با یک کلیک)
- **اندروید (Chrome):** آدرس اپ را باز کنید → منوی ⋮ → **Add to Home screen** → Add.
- **آیفون (Safari):** آدرس را باز کنید → دکمه اشتراک‌گذاری → **Add to Home Screen** → Add.
میانبر مثل یک اپ مستقل و تمام‌صفحه اجرا می‌شود.

## فایل‌ها
| فایل | نقش |
|---|---|
| `app.py` | رابط کاربری Streamlit (تنظیمات، اسکن، نمودارها) |
| `scoring.py` | موتور امتیازدهی، بلوک‌ها، گیت‌ها، فیلتر HTF، پلن معامله |
| `my_crypto_lib.py` | اندیکاتورها (EMA/RSI/MACD/ADX/ATR/BB/Ichimoku) |
| `kalman.py` | فیلتر کالمن و مشتق هموارشده قیمت |
| `data_sources.py` | رتبه‌بندی نمادها و دریافت OHLCV با fallback صرافی |
| `config.json` | وزن‌ها، آستانه‌ها، تایم‌فریم‌ها |
