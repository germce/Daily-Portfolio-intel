#!/usr/bin/env python3 import os, sys, time, html, json, smtplib, ssl from email.mime.text import MIMEText from datetime import datetime, timedelta import feedparser from dateutil import tz from dateutil.parser import parse as dtparse import yaml from jinja2 import Template import urllib.parse as urlparse
def domain_of(link): try: return urlparse.urlparse(link).hostname or "" except Exception: return ""
def load_yaml(path): with open(path, "r", encoding="utf-8") as f: return yaml.safe_load(f)
def fetch_feed(url): fp = feedparser.parse(url) return fp.entries or []
def within_window(published, since_utc): if not published: return False try: dt = dtparse(published) if not dt.tzinfo: dt = dt.replace(tzinfo=tz.UTC) return dt >= since_utc except Exception: return False
def unique_by_link(items): seen = set() out = [] for it in items: link = getattr(it, "link", "") or it.get("link", "") if link and link not in seen: seen.add(link) out.append(it) return out
HTML_TMPL = """
body{font-family:-apple-system,Helvetica,Arial,sans-serif;line-height:1.45;padding:16px;color:#111} h1{font-size:22px;margin:0 0 12px} h2{font-size:18px;margin:22px 0 8px} h3{font-size:15px;margin:12px 0 6px} ul{margin:6px 0 14px;padding-left:18px} li{margin:5px 0} small{color:#666} .section{border-top:1px solid #eee;padding-top:10px;margin-top:18px} .source{color:#666;font-size:12px}
{{ subject }}
{% for t in sections %}
{{ t.company }} ({{ t.ticker }})
{% if t.news %}
News
{% for it in t.news %}
{{ it.title | e }} [blocked]
{{ it.domain }} — {{ it.when }}
{% endfor %}
{% endif %} {% if t.filings %}
Filings
{% for it in t.filings %}
{{ it.title | e }} [blocked]
{{ it.domain }} — {{ it.when }}
{% endfor %}
{% endif %} {% if t.patents %}
Patents
{% for it in t.patents %}
{{ it.title | e }} [blocked]
{{ it.domain }} — {{ it.when }}
{% endfor %}
{% endif %}
{% endfor %}
Generated {{ generated_local }} """
def fmt_when(dt): return dt.strftime("%a, %d %b %Y %H:%M")
def main(): cfg = load_yaml("feeds.yml") tzname = cfg.get("timezone", "Europe/Zurich") tz_local = tz.gettz(tzname) now_utc = datetime.utcnow().replace(tzinfo=tz.UTC) since_utc = now_utc - timedelta(hours=24)


sections = []
for ticker, meta in cfg.get("tickers", {}).items():
    company = meta.get("name", ticker)
    cat_items = {"news": [], "filings": [], "patents": []}
    for cat in ["news", "filings", "patents"]:
        urls = meta.get(cat, []) or []
        items = []
        for u in urls:
            try:
                entries = fetch_feed(u)
                items.extend(entries)
            except Exception:
                pass
        # filter window
        kept = []
        for e in items:
            title = getattr(e, "title", "") or e.get("title", "")
            link  = getattr(e, "link", "")  or e.get("link", "")
            published = getattr(e, "published", "") or e.get("published", "") or getattr(e, "updated", "") or e.get("updated", "")
            if within_window(published, since_utc):
                kept.append({
                    "title": title.strip() if title else "(no title)",
                    "link": link,
                    "published": published
                })
        # dedupe and sort
        dedup = []
        seen = set()
        for it in kept:
            if it["link"] and it["link"] not in seen:
                seen.add(it["link"])
                dedup.append(it)
        dedup.sort(key=lambda x: dtparse(x["published"]), reverse=True)
        # map presentation
        out = []
        for it in dedup:
            d = domain_of(it["link"])
            local_dt = dtparse(it["published"]).astimezone(tz_local)
            out.append({
                "title": it["title"],
                "link": it["link"],
                "domain": d or "",
                "when": fmt_when(local_dt)
            })
        cat_items[cat] = out
    # only add section if any category has items
    if any(cat_items[c] for c in cat_items):
        sections.append({
            "ticker": ticker,
            "company": company,
            "news": cat_items["news"],
            "filings": cat_items["filings"],
            "patents": cat_items["patents"],
        })
subject_prefix = cfg.get("email", {}).get("subject_prefix", "Daily Portfolio Brief")
date_str = datetime.now(tz_local).strftime("%A, %d %b %Y")
subject = f"{subject_prefix} — {date_str}"
generated_local = datetime.now(tz_local).strftime("%Y-%m-%d %H:%M")
html = Template(HTML_TMPL).render(
    subject=subject,
    sections=sections,
    generated_local=generated_local
)
# send via Resend
api_key = os.environ.get("RESEND_API_KEY") mail_to = cfg.get("email", {}).get("to") if not api_key or not mail_to: print("Missing RESEND_API_KEY or recipient email.", file=sys.stderr) sys.exit(1) import requests, json payload = { "from": "Daily Brief notifications@resend.dev", "to": [mail_to], "subject": subject, "html": html } r = requests.post( "
api.resend.com
", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, data=json.dumps(payload), timeout=20 ) if r.status_code >= 300: print(f"Resend API error: {r.status_code} {r.text}", file=sys.stderr) sys.exit(1)

