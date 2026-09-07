import tkinter as tk
from tkinter import ttk
import requests
import threading
import time
import traceback
from datetime import datetime

REFRESH_SECONDS = 10
TIMEOUT = 8

# Public endpoints: no API keys are required.
NOBITEX_URL = "https://apiv2.nobitex.ir/v3/orderbook/USDTIRT"
BINANCE_URL = "https://api.binance.com/api/v3/ticker/price"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

session = requests.Session()
session.headers.update({"User-Agent": "MarketLiveTester/1.0"})

log_lines = []

def log(msg):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    log_lines.append(line)
    if len(log_lines) > 500:
        del log_lines[:-500]
    root.after(0, lambda: log_box.insert("end", line + "\n"))
    root.after(0, lambda: log_box.see("end"))

def http_get(url, **kwargs):
    r = session.get(url, timeout=TIMEOUT, **kwargs)
    r.raise_for_status()
    return r

def nobitex_usdt_irt():
    r = http_get(NOBITEX_URL)
    data = r.json()
    asks = data.get("asks", [])
    bids = data.get("bids", [])
    if not asks or not bids:
        raise RuntimeError("Nobitex returned no bids/asks")
    ask = float(asks[0][0])
    bid = float(bids[0][0])
    return (bid + ask) / 2.0, {"bid": bid, "ask": ask}

def binance_usdt(symbol):
    r = http_get(BINANCE_URL, params={"symbol": symbol + "USDT"})
    return float(r.json()["price"]), {}

def yahoo_last(symbol):
    r = http_get(
        YAHOO_URL.format(symbol=symbol),
        params={"range": "1d", "interval": "1m"}
    )
    j = r.json()
    result = j["chart"]["result"][0]
    meta = result.get("meta", {})
    price = meta.get("regularMarketPrice")
    if price is None:
        closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        closes = [x for x in closes if x is not None]
        if not closes:
            raise RuntimeError(f"No price returned for {symbol}")
        price = closes[-1]
    return float(price), {}

def format_irr(x):
    return f"{x:,.0f} ریال"

def format_usd(x):
    return f"${x:,.4f}"

def set_value(name, value, status="OK"):
    root.after(0, lambda: values[name].config(text=value))
    root.after(0, lambda: statuses[name].config(text=status))

def update_market():
    global updating
    if updating:
        return
    updating = True
    log("---- شروع به‌روزرسانی ----")

    def worker():
        try:
            # USDT/IRT from Nobitex. This endpoint is public and needs no key.
            try:
                usdt_irt, nb = nobitex_usdt_irt()
                set_value("تتر", format_irr(usdt_irt))
                set_value("دلار", format_irr(usdt_irt), "≈ تتر")
                log(f"Nobitex OK | USDT/IRT mid={usdt_irt:,.0f} | bid={nb['bid']:,.0f} ask={nb['ask']:,.0f}")
            except Exception as e:
                set_value("تتر", "ERROR", "Nobitex")
                set_value("دلار", "ERROR", "Nobitex")
                log(f"Nobitex ERROR: {type(e).__name__}: {e}")
                usdt_irt = None

            # Gold, silver and WTI from Yahoo Finance chart endpoint.
            yahoo_symbols = {
                "طلا": "GC=F",      # Gold futures, USD / troy oz
                "نقره": "SI=F",     # Silver futures, USD / troy oz
                "نفت": "CL=F",      # WTI crude oil, USD / barrel
            }
            yahoo_prices = {}
            for name, symbol in yahoo_symbols.items():
                try:
                    p, _ = yahoo_last(symbol)
                    yahoo_prices[name] = p
                    log(f"Yahoo OK | {symbol}={p}")
                except Exception as e:
                    log(f"Yahoo ERROR | {symbol}: {type(e).__name__}: {e}")

            if usdt_irt:
                if "طلا" in yahoo_prices:
                    # 1 troy oz = 31.1034768 grams; 18K = 75% pure gold.
                    gold18_irr = yahoo_prices["طلا"] / 31.1034768 * 0.75 * usdt_irt
                    set_value("طلا", format_irr(gold18_irr), "18K/gram")
                    log(f"Gold calculated | raw ounce=${yahoo_prices['طلا']:.4f} | 18K/g={gold18_irr:,.0f} IRR")
                else:
                    set_value("طلا", "ERROR", "Yahoo")

                if "نقره" in yahoo_prices:
                    silver_gram_irr = yahoo_prices["نقره"] / 31.1034768 * usdt_irt
                    set_value("نقره", format_irr(silver_gram_irr), "pure/g")
                    log(f"Silver calculated | raw ounce=${yahoo_prices['نقره']:.4f} | g={silver_gram_irr:,.0f} IRR")
                else:
                    set_value("نقره", "ERROR", "Yahoo")

                if "نفت" in yahoo_prices:
                    oil_irr = yahoo_prices["نفت"] * usdt_irt
                    set_value("نفت", format_irr(oil_irr), "WTI/barrel")
                    log(f"Oil calculated | WTI=${yahoo_prices['نفت']:.4f} | {oil_irr:,.0f} IRR/barrel")
                else:
                    set_value("نفت", "ERROR", "Yahoo")

            # Crypto in USD via Binance, then convert to IRR.
            for name, symbol in [("بیت‌کوین", "BTC"), ("اتریوم", "ETH")]:
                try:
                    p, _ = binance_usdt(symbol)
                    if usdt_irt:
                        irr = p * usdt_irt
                        set_value(name, format_irr(irr), f"${p:,.2f}")
                        log(f"Binance OK | {symbol}/USDT={p:.6f} | IRR={irr:,.0f}")
                    else:
                        set_value(name, format_usd(p), "USD/USDT unavailable")
                except Exception as e:
                    set_value(name, "ERROR", "Binance")
                    log(f"Binance ERROR | {symbol}: {type(e).__name__}: {e}")

        except Exception:
            log("UNEXPECTED ERROR:\n" + traceback.format_exc())
        finally:
            root.after(0, finish_update)

    threading.Thread(target=worker, daemon=True).start()

def finish_update():
    global updating
    updating = False
    last_update.config(text="آخرین تلاش: " + datetime.now().strftime("%H:%M:%S"))
    root.after(REFRESH_SECONDS * 1000, update_market)

def copy_logs():
    text = "\n".join(log_lines)
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update()
    log("لاگ‌ها در Clipboard کپی شدند.")

def clear_logs():
    log_lines.clear()
    log_box.delete("1.0", "end")
    log("لاگ پاک شد.")

root = tk.Tk()
root.title("Market Live Tester — بدون API Key")
root.geometry("920x700")
root.minsize(820, 620)

style = ttk.Style()
try:
    style.theme_use("clam")
except Exception:
    pass

header = ttk.Frame(root, padding=12)
header.pack(fill="x")

ttk.Label(
    header,
    text="Live Market Tester",
    font=("Segoe UI", 20, "bold")
).pack(side="left")

ttk.Label(
    header,
    text=f"به‌روزرسانی خودکار هر {REFRESH_SECONDS} ثانیه",
).pack(side="right")

frame = ttk.Frame(root, padding=(12, 0, 12, 8))
frame.pack(fill="x")

values = {}
statuses = {}

items = [
    ("تتر", "USDT/IRT"),
    ("دلار", "≈ USDT/IRT"),
    ("طلا", "18K / gram / IRR"),
    ("نقره", "pure / gram / IRR"),
    ("نفت", "WTI / barrel / IRR"),
    ("بیت‌کوین", "BTC / IRR"),
    ("اتریوم", "ETH / IRR"),
]

for i, (name, subtitle) in enumerate(items):
    card = ttk.LabelFrame(frame, text=name, padding=10)
    card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=1)

    values[name] = ttk.Label(card, text="در حال دریافت...", font=("Segoe UI", 15, "bold"))
    values[name].pack(anchor="w")
    ttk.Label(card, text=subtitle).pack(anchor="w", pady=(3, 0))
    statuses[name] = ttk.Label(card, text="WAIT")
    statuses[name].pack(anchor="w")

# Make last card span both columns.
# (The grid above already placed it in row 3, col 0.)
log_frame = ttk.LabelFrame(root, text="لاگ فنی — برای ارسال به ChatGPT", padding=8)
log_frame.pack(fill="both", expand=True, padx=12, pady=8)

log_box = tk.Text(log_frame, height=14, wrap="word", font=("Consolas", 9))
log_box.pack(fill="both", expand=True, side="left")

scroll = ttk.Scrollbar(log_frame, orient="vertical", command=log_box.yview)
scroll.pack(side="right", fill="y")
log_box.configure(yscrollcommand=scroll.set)

buttons = ttk.Frame(root, padding=(12, 0, 12, 12))
buttons.pack(fill="x")

ttk.Button(buttons, text="کپی کل لاگ‌ها به Clipboard", command=copy_logs).pack(side="left", padx=(0, 8))
ttk.Button(buttons, text="پاک کردن لاگ", command=clear_logs).pack(side="left", padx=8)
ttk.Button(buttons, text="به‌روزرسانی فوری", command=update_market).pack(side="right")

last_update = ttk.Label(root, text="آخرین تلاش: --:--:--", padding=(12, 0, 12, 8))
last_update.pack(anchor="w")

updating = False
log("برنامه شروع شد.")
log("منابع: Nobitex (USDT/IRT) + Yahoo Finance (Gold/Silver/WTI) + Binance (BTC/ETH).")
log("این نسخه برای تست اولیه هیچ API Key نمی‌خواهد.")

root.after(200, update_market)
root.mainloop()
