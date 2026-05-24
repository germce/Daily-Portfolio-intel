import json
import os
import yfinance as yf
import resend
from datetime import date

# Load tickers
with open("tickers.json") as f:
    tickers = json.load(f)  # expects a list like ["AAPL", "MSFT", "TSLA"]

# Fetch stock data
rows = []
for symbol in tickers:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = round(info.last_price, 2)
        prev_close = round(info.previous_close, 2)
        change = round(price - prev_close, 2)
        pct = round((change / prev_close) * 100, 2)
        arrow = "🟢" if change >= 0 else "🔴"
        rows.append({
            "symbol": symbol,
            "price": price,
            "change": change,
            "pct": pct,
            "arrow": arrow,
        })
    except Exception as e:
        rows.append({"symbol": symbol, "error": str(e)})

# Build HTML email
today = date.today().strftime("%B %d, %Y")
table_rows = ""
for r in rows:
    if "error" in r:
        table_rows += f"<tr><td>{r['symbol']}</td><td colspan='3' style='color:gray'>Error: {r['error']}</td></tr>"
    else:
        color = "#16a34a" if r["change"] >= 0 else "#dc2626"
        table_rows += f"""
        <tr>
          <td style='padding:8px 12px;font-weight:bold'>{r['arrow']} {r['symbol']}</td>
          <td style='padding:8px 12px'>${r['price']}</td>
          <td style='padding:8px 12px;color:{color}'>{'+' if r['change'] >= 0 else ''}{r['change']}</td>
          <td style='padding:8px 12px;color:{color}'>{'+' if r['pct'] >= 0 else ''}{r['pct']}%</td>
        </tr>"""

html = f"""
<html><body style='font-family:sans-serif;max-width:600px;margin:auto'>
  <h2>📈 Portfolio Update — {today}</h2>
  <table style='width:100%;border-collapse:collapse;border:1px solid #e5e7eb'>
    <thead>
      <tr style='background:#f3f4f6;text-align:left'>
        <th style='padding:8px 12px'>Ticker</th>
        <th style='padding:8px 12px'>Price</th>
        <th style='padding:8px 12px'>Change</th>
        <th style='padding:8px 12px'>% Change</th>
      </tr>
    </thead>
    <tbody>{table_rows}</tbody>
  </table>
  <p style='color:#9ca3af;font-size:12px;margin-top:16px'>Data via Yahoo Finance · Sent by GitHub Actions</p>
</body></html>
"""

# Send via Resend
resend.api_key = os.environ["RESEND_API_KEY"]
resend.Emails.send({
    "from": os.environ["FROM_EMAIL"],
    "to": os.environ["TO_EMAIL"],
    "subject": f"📈 Portfolio Update — {today}",
    "html": html,
})

print("Email sent successfully.")
