# Market Live Tester

نسخه تست اولیه برای نمایش:
- USDT/IRT
- USD/IRT (تقریباً برابر USDT/IRT)
- طلای ۱۸ عیار / گرم / ریال
- نقره / گرم / ریال
- نفت WTI / بشکه / ریال
- Bitcoin / ریال
- Ethereum / ریال

## API Key
این نسخه عمداً از endpointهای عمومی استفاده می‌کند و برای تست اولیه API Key نمی‌خواهد.

منابع:
- Nobitex public orderbook: USDTIRT
- Yahoo Finance chart endpoint: GC=F, SI=F, CL=F
- Binance public ticker: BTCUSDT, ETHUSDT

## اجرا
```bash
python -m pip install -r requirements.txt
python market_live_tester.py
```

اگر روی Windows دستور `python` کار نکرد:
```bash
py -m pip install -r requirements.txt
py market_live_tester.py
```

## لاگ
دکمه «کپی کل لاگ‌ها به Clipboard» تمام لاگ‌های درخواست‌ها، پاسخ‌های موفق و خطاها را کپی می‌کند.
اگر چیزی کار نکرد، کل لاگ را برای ChatGPT بفرست.

## نکته
قیمت طلا و نقره از اونس تروا به گرم تبدیل می‌شود:
1 troy oz = 31.1034768 g

طلای ۱۸ عیار:
Gold USD/oz / 31.1034768 * 0.75 * USDT/IRT

این عدد قیمت خام تئوریک است و شامل اجرت، مالیات، حباب و اختلاف بازار طلای ایران نیست.
