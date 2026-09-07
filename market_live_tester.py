import tkinter as tk
from tkinter import ttk
import requests
import threading
import time
import traceback
from datetime import datetime

REFRESH_SECONDS = 10
TIMEOUT = 8

# Tehran Stock Exchange / Iran Fara Bourse symbols requested by the user.
# TSETMC provides a bulk market-watch endpoint, so we fetch all of them in one call.
WEBGW_CASH_URL = "https://webgw.tse.ir/InstrumentProvider/api/v1/MarketWatch/MarketWatchCash/fa"
WEBGW_ETF_URL = "https://webgw.tse.ir/InstrumentProvider/api/v1/MarketWatch/MarketWatchEtf/fa"

IRAN_SYMBOLS = [
    ("کارا", "کارا"), ("یاقوت", "یاقوت"), ("آوند", "آوند"),
    ("پاسارگاد", "وپاسار"), ("سبپ", "سبپ"), ("عیار", "عیار"),
    ("اطلس", "اطلس"), ("آگاس", "آگاس"), ("سیمانو", "سیمانو"),
    ("دارا یکم", "دارا یکم"), ("اهرم", "اهرم"), ("توان", "توان"),
    ("وبملت", "وبملت"), ("وتجارت", "وتجارت"), ("خودرو", "خودرو"),
    ("وبصادر", "وبصادر"), ("خساپا", "خساپا"),
]

# Public endpoints: no API keys required for this tester.
NOBITEX_URL = "https://apiv2.nobitex.ir/v3/orderbook/USDTIRT"
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

session = requests.Session()
session.headers.update({"User-Agent": "MarketLiveTester/2.0"})

log_lines = []
updating = False

def log(msg):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    log_lines.append(line)
    if len(log_lines) > 1000:
        del log_lines[:-1000]
    root.after(0, lambda: append_log(line))

def append_log(line):
    log_box.insert("end", line + "\n")
    log_box.see("end")

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
    return (bid + ask) / 2.0, bid, ask

def coingecko_prices():
    r = http_get(
        COINGECKO_URL,
        params={
            "ids": "bitcoin,ethereum",
            "vs_currencies": "usd"
        }
    )
    data = r.json()
    return float(data["bitcoin"]["usd"]), float(data["ethereum"]["usd"])

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
    return float(price)



def yahoo_fx_eurusd():
    """EUR/USD from Yahoo; converted to IRR using the local USDT/IRR rate."""
    return yahoo_last("EURUSD=X")


def normalize_fa(text):
    text = str(text or "").strip()
    return (text.replace("ي", "ی").replace("ك", "ک")
                .replace("_", "").replace(" ", "")
                .replace("\u200c", "").replace("\u200f", ""))

def webgw_marketwatch(url, kind):
    r = http_get(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.tse.ir/",
    })
    data = r.json()
    rows = data.get("Items", []) if isinstance(data, dict) else []
    if not isinstance(rows, list):
        raise RuntimeError(f"TSE webgw {kind} returned unexpected JSON")
    return rows

def tsetmc_marketwatch():
    """Use the official tse.ir web gateway. Cash and ETF are separate feeds."""
    rows = []
    errors = []
    for url, kind in ((WEBGW_CASH_URL, "Cash"), (WEBGW_ETF_URL, "ETF")):
        try:
            got = webgw_marketwatch(url, kind)
            rows.extend(got)
            log(f"TSE webgw OK | {kind} items={len(got)}")
        except Exception as e:
            errors.append(f"{kind}: {type(e).__name__}: {e}")
            log(f"TSE webgw ERROR | {kind}: {type(e).__name__}: {e}")

    if not rows:
        raise RuntimeError("Both TSE webgw Cash/ETF feeds returned no data")

    wanted = {normalize_fa(query) for _, query in IRAN_SYMBOLS}
    out = {}
    for row in rows:
        symbol = row.get("instrumentName") or row.get("instrument_Name") or row.get("symbol") or ""
        symbol_n = normalize_fa(symbol)
        if symbol_n not in wanted:
            continue

        # Official webgw uses lastPrice.value in current responses.
        lp = row.get("lastPrice")
        price = lp.get("value") if isinstance(lp, dict) else lp
        if price is None:
            price = row.get("lastprice")
        if isinstance(price, dict):
            price = price.get("value")
        if price is None:
            cp = row.get("closingPrice")
            price = cp.get("value") if isinstance(cp, dict) else cp

        if price is None:
            continue
        try:
            out[symbol_n] = {
                "price": float(price),
                "symbol": str(symbol).strip(),
                "name": row.get("companyNamePersian") or row.get("company_Name_Persian") or "",
                "change": ((lp or {}).get("percent") if isinstance(lp, dict) else ""),
            }
        except (TypeError, ValueError):
            continue

    return out

def format_irr(x):
    return f"{x:,.0f} ریال"

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
        usdt_irt = None

        # 1) USDT/IRR
        try:
            usdt_irt, bid, ask = nobitex_usdt_irt()
            set_value("تتر", format_irr(usdt_irt))
            set_value("دلار", format_irr(usdt_irt), "≈ USDT")
            log(f"Nobitex OK | USDT/IRT mid={usdt_irt:,.0f} | bid={bid:,.0f} ask={ask:,.0f}")
        except Exception as e:
            set_value("تتر", "ERROR", "Nobitex")
            set_value("دلار", "ERROR", "Nobitex")
            log(f"Nobitex ERROR: {type(e).__name__}: {e}")

        # 2) Gold / Silver / WTI
        yahoo_symbols = {
            "طلا": "GC=F",
            "نقره": "SI=F",
            "نفت": "CL=F",
        }
        yahoo_prices = {}
        for name, symbol in yahoo_symbols.items():
            try:
                p = yahoo_last(symbol)
                yahoo_prices[name] = p
                log(f"Yahoo OK | {symbol}={p}")
            except Exception as e:
                set_value(name, "ERROR", "Yahoo")
                log(f"Yahoo ERROR | {symbol}: {type(e).__name__}: {e}")

        if usdt_irt:
            if "طلا" in yahoo_prices:
                gold18_irr = yahoo_prices["طلا"] / 31.1034768 * 0.75 * usdt_irt
                set_value("طلا", format_irr(gold18_irr), "18K/gram")
                log(f"Gold calculated | ${yahoo_prices['طلا']:.4f}/oz | 18K/g={gold18_irr:,.0f} IRR")

            if "نقره" in yahoo_prices:
                silver_gram_irr = yahoo_prices["نقره"] / 31.1034768 * usdt_irt
                set_value("نقره", format_irr(silver_gram_irr), "pure/g")
                log(f"Silver calculated | ${yahoo_prices['نقره']:.4f}/oz | g={silver_gram_irr:,.0f} IRR")

            if "نفت" in yahoo_prices:
                oil_irr = yahoo_prices["نفت"] * usdt_irt
                set_value("نفت", format_irr(oil_irr), "WTI/barrel")
                log(f"Oil calculated | WTI=${yahoo_prices['نفت']:.4f} | {oil_irr:,.0f} IRR/barrel")

        # 3) EUR/USD -> EUR/IRR
        try:
            eurusd = yahoo_fx_eurusd()
            log(f"Yahoo OK | EURUSD={eurusd:.6f}")
            if usdt_irt:
                eur_irr = eurusd * usdt_irt
                set_value("یورو", format_irr(eur_irr), f"EURUSD={eurusd:.4f}")
                log(f"EUR calculated | EUR/USD={eurusd:.6f} | EUR/IRR={eur_irr:,.0f}")
        except Exception as e:
            set_value("یورو", "ERROR", "Yahoo")
            log(f"Yahoo ERROR | EURUSD=X: {type(e).__name__}: {e}")

        # 4) Tehran Stock Exchange / IFB symbols via one bulk TSETMC request
        try:
            stock_data = tsetmc_marketwatch()
            for display_name, query_name in IRAN_SYMBOLS:
                item = stock_data.get(query_name)
                if item is None:
                    set_value(display_name, "N/A", "TSETMC")
                    log(f"TSETMC NOT FOUND | {display_name} (query={query_name})")
                    continue
                set_value(display_name, format_irr(item["price"]), "آخرین معامله")
                log(f"TSETMC OK | {display_name}/{item['symbol']}={item['price']:,.0f} IRR")
        except Exception as e:
            for display_name, _ in IRAN_SYMBOLS:
                set_value(display_name, "ERROR", "TSETMC")
            log(f"TSETMC ERROR: {type(e).__name__}: {e}")

        # 5) BTC / ETH via CoinGecko (replacing Binance)
        try:
            btc_usd, eth_usd = coingecko_prices()
            log(f"CoinGecko OK | BTC=${btc_usd:,.2f} | ETH=${eth_usd:,.2f}")

            if usdt_irt:
                btc_irr = btc_usd * usdt_irt
                eth_irr = eth_usd * usdt_irt
                set_value("بیت‌کوین", format_irr(btc_irr), f"${btc_usd:,.2f}")
                set_value("اتریوم", format_irr(eth_irr), f"${eth_usd:,.2f}")
                log(f"BTC calculated | {btc_irr:,.0f} IRR")
                log(f"ETH calculated | {eth_irr:,.0f} IRR")
            else:
                set_value("بیت‌کوین", f"${btc_usd:,.2f}", "USD")
                set_value("اتریوم", f"${eth_usd:,.2f}", "USD")
        except Exception as e:
            set_value("بیت‌کوین", "ERROR", "CoinGecko")
            set_value("اتریوم", "ERROR", "CoinGecko")
            log(f"CoinGecko ERROR: {type(e).__name__}: {e}")

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
root.title("Market Live Tester v4")
root.geometry("1000x850")
root.minsize(900, 720)

style = ttk.Style()
try:
    style.theme_use("clam")
except Exception:
    pass

# Compact header
header = ttk.Frame(root, padding=(10, 8))
header.pack(fill="x")
ttk.Label(header, text="Live Market Tester v2",
          font=("Segoe UI", 17, "bold")).pack(side="left")
ttk.Label(header, text=f"Auto refresh: {REFRESH_SECONDS}s",
          font=("Segoe UI", 9)).pack(side="right")

# Compact 7-card grid: 4 columns to save vertical space.
cards = ttk.Frame(root, padding=(10, 0, 10, 4))
cards.pack(fill="x")
for c in range(4):
    cards.columnconfigure(c, weight=1)

items = [
    ("تتر", "USDT/IRT"),
    ("دلار", "≈ USDT/IRT"),
    ("یورو", "EUR/IRR"),
    ("طلا", "18K / gram"),
    ("نقره", "pure / gram"),
    ("نفت", "WTI / barrel"),
    ("بیت‌کوین", "BTC / IRR"),
    ("اتریوم", "ETH / IRR"),
]

values = {}
statuses = {}

for i, (name, subtitle) in enumerate(items):
    row, col = divmod(i, 4)
    card = ttk.LabelFrame(cards, text=name, padding=(8, 5))
    card.grid(row=row, column=col, sticky="nsew", padx=4, pady=3)

    values[name] = ttk.Label(card, text="در حال دریافت...",
                             font=("Segoe UI", 11, "bold"))
    values[name].pack(anchor="w")

    ttk.Label(card, text=subtitle, font=("Segoe UI", 8)).pack(anchor="w")
    statuses[name] = ttk.Label(card, text="WAIT", font=("Segoe UI", 8))
    statuses[name].pack(anchor="w")

# Give empty 8th cell no height impact.
for c in range(4):
    cards.columnconfigure(c, weight=1)

# Requested Tehran market symbols
stocks_frame = ttk.LabelFrame(root, text="بورس / فرابورس ایران — آخرین معامله", padding=(6, 4))
stocks_frame.pack(fill="x", padx=10, pady=(2, 3))
for c in range(6):
    stocks_frame.columnconfigure(c, weight=1)

for i, (display_name, _) in enumerate(IRAN_SYMBOLS):
    row, col = divmod(i, 6)
    card = ttk.LabelFrame(stocks_frame, text=display_name, padding=(6, 3))
    card.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
    values[display_name] = ttk.Label(card, text="در حال دریافت...", font=("Segoe UI", 9, "bold"))
    values[display_name].pack(anchor="w")
    statuses[display_name] = ttk.Label(card, text="TSETMC", font=("Segoe UI", 7))
    statuses[display_name].pack(anchor="w")

# Log gets most of the window.
log_frame = ttk.LabelFrame(root, text="لاگ فنی — برای ارسال به ChatGPT", padding=6)
log_frame.pack(fill="both", expand=True, padx=10, pady=(3, 5))

log_box = tk.Text(
    log_frame,
    wrap="none",
    font=("Consolas", 9),
    height=30
)
log_box.pack(side="left", fill="both", expand=True)

scroll_y = ttk.Scrollbar(log_frame, orient="vertical", command=log_box.yview)
scroll_y.pack(side="right", fill="y")

scroll_x = ttk.Scrollbar(root, orient="horizontal", command=log_box.xview)
scroll_x.pack(fill="x", padx=10)

log_box.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

# Buttons
buttons = ttk.Frame(root, padding=(10, 2, 10, 5))
buttons.pack(fill="x")

ttk.Button(buttons, text="کپی کل لاگ‌ها به Clipboard",
           command=copy_logs).pack(side="left", padx=(0, 6))
ttk.Button(buttons, text="پاک کردن لاگ",
           command=clear_logs).pack(side="left", padx=6)
ttk.Button(buttons, text="به‌روزرسانی فوری",
           command=update_market).pack(side="right")

last_update = ttk.Label(root, text="آخرین تلاش: --:--:--",
                        padding=(10, 0, 10, 6))
last_update.pack(anchor="w")

log("برنامه شروع شد.")
log("v4: Nobitex + Yahoo + CoinGecko + TSE official web gateway (Cash + ETF).")
log("Binance حذف شد چون HTTP 451 می‌داد.")
log("TSE symbols now use webgw.tse.ir Cash/ETF bulk feeds instead of the old CDN market-watch endpoint.")
log("این نسخه برای تست اولیه هیچ API Key نمی‌خواهد.")

root.after(200, update_market)
root.mainloop()
