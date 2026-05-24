import json
import os
import time
import yfinance as yf
import resend
from datetime import date, datetime, timezone

# Load tickers
with open("tickers.json") as f:
    tickers = json.load(f)  # e.g. ["AAPL", "MSFT", "TSLA"]

MAX_NEWS = 5  # max news items per ticker

# Fetch stock data + news
stocks = []
for symbol in tickers:
    entry = {"symbol": symbol}
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = round(info.last_price, 2)
        prev_close = round(info.previous_close, 2)
        change = round(price - prev_close, 2)
        pct = round((change / prev_close) * 100, 2)
        entry.update({
            "price": price,
            "change": change,
            "pct": pct,
            "arrow": "🟢" if change >= 0 else "🔴",
        })
    except Exception as e:
        entry["price_error"] = str(e)

    try:
        raw_news = ticker.news or []
        news_items = []
        for item in raw_news[:MAX_NEWS]:
            content = item.get("content", {})
            title = content.get("title") or item.get("title", "No title")
            url = (
                content.get("canonicalUrl", {}).get("url")
                or content.get("clickThroughUrl", {}).get("url")
                or item.get("link", "#")
            )
            pub_ts = content.get("pubDate") or item.get("providerPublishTime")
            if isinstance(pub_ts, str):
                try:
                    pub_date = datetime.fromisoformat(pub_ts.replace("Z", "+00:00")).strftime("%b %d")
                except Exception:
                    pub_date = pub_ts[:10]
            elif isinstance(pub_ts, (int, float)):
                pub_date = datetime.fromtimestamp(pub_ts, tz=timezone.utc).strftime("%b %d")
            else:
                pub_date = ""
            publisher = content.get("provider", {}).get("displayName") or item.get("publisher", "")
            news_items.append({"title": title, "url": url, "date": pub_date, "publisher": publisher})
        entry["news"] = news_items
    except Exception as e:
        entry["news_error"] = str(e)
        entry["news"] = []

    stocks.append(entry)
    time.sleep(0.4)  # be kind to Yahoo's rate limits

# ── HTML builder helpers ──────────────────────────────────────────────────────

def price_row(r):
    if "price_error" in r:
        return f"<tr><td><b>{r['symbol']}</b></td><td colspan='3' style='color:#9ca3af'>Price unavailable: {r['price_error']}</td></tr>"
    color = "#16a34a" if r["change"] >= 0 else "#dc2626"
    sign = "+" if r["change"] >= 0 else ""
    return f"""
    <tr>
      <td style='padding:8px 12px;font-weight:bold'>{r['arrow']} {r['symbol']}</td>
      <td style='padding:8px 12px'>${r['price']}</td>
      <td style='padding:8px 12px;color:{color}'>{sign}{r['change']}</td>
      <td style='padding:8px 12px;color:{color}'>{sign}{r['pct']}%</td>
    </tr>"""

def news_section(r):
    symbol = r["symbol"]
    items = r.get("news", [])
    if not items and "news_error" in r:
        return f"<p style='color:#9ca3af;font-size:13px'>News unavailable for {symbol}: {r['news_error']}</p>"
    if not items:
        return f"<p style='color:#9ca3af;font-size:13px'>No recent news for {symbol}.</p>"

    bullets = ""
    for n in items:
        meta = f"<span style='color:#9ca3af;font-size:11px'> · {n['publisher']}" + (f" · {n['date']}" if n['date'] else "") + "</span>"
        bullets += f"<li style='margin-bottom:6px'><a href='{n['url']}' style='color:#2563eb;text-decoration:none'>{n['title']}</a>{meta}</li>"

    return f"""
    <div style='margin-bottom:24px'>
      <h3 style='margin:0 0 8px;font-size:15px;color:#111827'>{symbol} — Latest News</h3>
      <ul style='margin:0;padding-left:18px;line-height:1.6'>{bullets}</ul>
    </div>"""

# ── Assemble email ────────────────────────────────────────────────────────────

today = date.today().strftime("%B %d, %Y")

price_rows = "".join(price_row(s) for s in stocks)
news_sections = "".join(news_section(s) for s in stocks)

html = f"""
<html><body style='font-family:sans-serif;max-width:640px;margin:auto;color:#111827'>

  <h2 style='margin-bottom:4px'>📈 Portfolio Update — {today}</h2>
  <p style='color:#6b7280;margin-top:0;font-size:13px'>Prices vs. previous close · News via Yahoo Finance</p>

  <table style='width:100%;border-collapse:collapse;border:1px solid #e5e7eb;margin-bottom:32px'>
    <thead>
      <tr style='background:#f3f4f6;text-align:left'>
        <th style='padding:8px 12px'>Ticker</th>
        <th style='padding:8px 12px'>Price</th>
        <th style='padding:8px 12px'>Change</th>
        <th style='padding:8px 12px'>% Change</th>
      </tr>
    </thead>
    <tbody>{price_rows}</tbody>
  </table>

  <h2 style='margin-bottom:16px'>📰 News & Announcements</h2>
  {news_sections}

  <hr style='border:none;border-top:1px solid #e5e7eb;margin:24px 0'>
  <p style='color:#9ca3af;font-size:11px'>Sent automatically by GitHub Actions · Data via Yahoo Finance · {today}</p>

</body></html>
"""

# ── Send via Resend ───────────────────────────────────────────────────────────

resend.api_key = os.environ["RESEND_API_KEY"]
resend.Emails.send({
    "from": os.environ["FROM_EMAIL"],
    "to": os.environ["TO_EMAIL"],
    "subject": f"📈 Portfolio Update — {today}",
    "html": html,
})

print(f"Email sent successfully for {len(stocks)} tickers.")
