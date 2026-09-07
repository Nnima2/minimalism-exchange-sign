# Market Live Tester v2

نسخه دوم تستر قیمت بازار.

دارایی‌ها:
- USDT/IRT
- USD/IRT (فعلاً به صورت تقریب USDT/IRT)
- طلای ۱۸ عیار / گرم / ریال
- نقره / گرم / ریال
- نفت WTI / بشکه / ریال
- Bitcoin / ریال
- Ethereum / ریال

منابع:
- Nobitex public orderbook برای USDT/IRT
- Yahoo Finance chart endpoint برای GC=F, SI=F, CL=F
- CoinGecko public API برای BTC و ETH
- Binance در v2 حذف شد چون در تست کاربر HTTP 451 می‌داد.

API Key:
این نسخه API Key نمی‌خواهد.

اجرا:
python -m pip install -r requirements.txt
python market_live_tester.py

Windows:
py -m pip install -r requirements.txt
py market_live_tester.py

UI:
کارت‌های قیمت کوچک‌تر و فشرده‌تر شده‌اند و لاگ بخش اصلی پنجره را می‌گیرد.
اسکرول عمودی و افقی برای لاگ وجود دارد.
دکمه کپی کل لاگ‌ها همه لاگ‌های ذخیره‌شده را در Clipboard می‌گذارد.

فرمول طلا:
Gold USD/oz / 31.1034768 * 0.75 * USDT/IRR

فرمول نقره:
Silver USD/oz / 31.1034768 * USDT/IRR

فرمول نفت:
WTI USD/barrel * USDT/IRR

فرمول BTC/ETH:
USD price * USDT/IRR

نکته:
قیمت طلای ۱۸ عیار محاسبه‌شده قیمت خام تئوریک است و شامل اجرت، مالیات، حباب و اختلاف بازار ایران نیست.
