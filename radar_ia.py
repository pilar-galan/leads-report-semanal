#!/usr/bin/env python3
import feedparser, requests, json, html, os, re
from datetime import datetime
from playwright.sync_api import sync_playwright

DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
ANTHROPIC_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")

DAYS_ES   = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
MONTHS_ES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
QUERIES = [
    ("SECTOR",      "🥇", "AI agents customer support CX innovation 2026"),
    ("COMPETENCIA", "🥈", "Intercom Decagon Sierra Ada Fin AI customer support startup funding"),
    ("TENDENCIAS",  "🥉", "customer experience AI trends report 2026"),
]

def format_date_es():
    n = datetime.now()
    return f"{DAYS_ES[n.weekday()]}, {n.day} de {MONTHS_ES[n.month-1]} de {n.year}"

def fetch_top_article(query):
    try:
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        if feed.entries:
            e = feed.entries[0]
            title   = html.unescape(re.sub(r"\s+-\s+\S.*$", "", e.title))
            summary = html.unescape(re.sub("<[^>]+>", "", e.get("summary", "")))[:600]
            return {"title": title, "link": e.link, "source": e.get("source", {}).get("title", "Google News"), "summary": summary}
    except Exception as err:
        print(f"  RSS error: {err}")
    return None

def analyze_with_claude(articles_raw):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        news_text = "\n\n".join(
            f"[{cat}]\nTítulo: {a['title']}\nFuente: {a['source']}\nResumen: {a['summary']}"
            for cat, _, a in articles_raw
        )
        prompt = f"""Eres el analista de GuruSup (startup española de AI agents para customer support, compite con Decagon, Sierra, Ada, Intercom Fin; ICP: startups B2C Series A-C España/LATAM 5k-50k tickets/mes).
Genera el resumen diario EN ESPAÑOL. Responde ÚNICAMENTE con este JSON exacto sin texto adicional:
{{"SECTOR":{{"title":"titular potente en español máx 90 chars","paragraph":"2-3 frases en español, máx 4 líneas, qué ha pasado y por qué importa","kpis":["dato/número impactante con contexto","dato/número impactante con contexto","dato/número impactante con contexto"],"recommendation":"1-2 frases: por qué le interesa a GuruSup y qué oportunidad/acción concreta tiene"}},"COMPETENCIA":{{"title":"...","paragraph":"...","kpis":["...","...","..."],"recommendation":"..."}},"TENDENCIAS":{{"title":"...","paragraph":"...","kpis":["...","...","..."],"recommendation":"..."}}}}
Noticias:\n{news_text}"""
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = re.sub(r"^```(?:json)?\s*\n?", "", resp.content[0].text.strip())
        raw = re.sub(r"\n?```\s*$", "", raw)
        result = json.loads(raw.strip())
        print(f"  Claude OK: {list(result.keys())}")
        return result
    except Exception as err:
        print(f"  Claude error: {err}")
        return {}

def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def generate_html(today, articles_raw, analysis):
    LABELS = {
        "SECTOR":      ("🥇", "SECTOR",      "#FF6B5B"),
        "COMPETENCIA": ("🥈", "COMPETENCIA", "#FF6B5B"),
        "TENDENCIAS":  ("🥉", "TENDENCIAS",  "#FF6B5B"),
    }

    cards_html = ""
    for cat, _, article in articles_raw:
        medal, label, accent = LABELS[cat]
        a     = analysis.get(cat, {})
        title = esc(a.get("title") or article["title"])
        para  = esc(a.get("paragraph") or article["summary"][:400])
        kpis  = a.get("kpis") or []
        rec   = esc(a.get("recommendation") or "")
        src   = esc(article["source"])
        link  = article["link"]

        kpi_rows = "".join(
            f'<tr><td style="padding:5px 0;vertical-align:top;">'
            f'<span style="color:#FF6B5B;font-weight:700;margin-right:6px;">•</span>'
            f'</td><td style="padding:5px 0;font-size:14px;color:#D1D5DB;line-height:1.5;">'
            f'{esc(k)}</td></tr>'
            for k in kpis
        )

        rec_block = ""
        if rec:
            rec_block = f'''
            <tr><td colspan="2" style="padding-top:14px;">
              <div style="border-top:1px solid #2D3748;margin-bottom:12px;"></div>
              <div style="font-size:13px;color:#9CA3AF;line-height:1.6;">
                <span style="font-size:16px;margin-right:6px;">💡</span>
                <strong style="color:#E5E7EB;">Por qué le interesa a GuruSup:</strong><br/>
                <span style="color:#CBD5E0;">{rec}</span>
              </div>
            </td></tr>'''

        cards_html += f'''
        <div style="background:#161B27;border-radius:10px;border-left:4px solid {accent};margin-bottom:16px;overflow:hidden;">
          <div style="padding:18px 20px 16px 20px;">
            <!-- Categoría -->
            <div style="margin-bottom:10px;">
              <span style="display:inline-block;background:#0D1117;color:{accent};font-size:11px;font-weight:800;
                           padding:4px 10px;border-radius:4px;letter-spacing:.1em;text-transform:uppercase;
                           border:1px solid {accent};">{medal} {label}</span>
            </div>
            <!-- Titular -->
            <div style="font-family:Georgia,serif;font-size:19px;font-weight:bold;color:#F9FAFB;
                        line-height:1.35;margin-bottom:8px;">{title}</div>
            <!-- Fuente -->
            <div style="font-size:12px;color:#6B7280;margin-bottom:12px;letter-spacing:.03em;">
              📰 Fuente: <a href="{link}" style="color:#9CA3AF;text-decoration:none;">{src}</a>
            </div>
            <!-- Descripción -->
            <div style="font-size:14px;color:#9CA3AF;line-height:1.65;margin-bottom:14px;">{para}</div>
            <!-- KPIs -->
            <table cellpadding="0" cellspacing="0" style="width:100%;margin-bottom:4px;">
              {kpi_rows}
              {rec_block}
            </table>
          </div>
        </div>'''

    return f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0A0E1A;font-family:Helvetica,Arial,sans-serif;">
<div style="width:720px;margin:0 auto;padding:20px;">

  <!-- BANNER -->
  <div style="background:#0D1117;border-radius:12px 12px 0 0;padding:28px 30px 22px;
              border-bottom:2px solid #FF6B5B;margin-bottom:0;">
    <table cellpadding="0" cellspacing="0" style="width:100%;">
      <tr>
        <td>
          <div style="color:#6B7280;font-size:11px;font-weight:600;letter-spacing:.15em;
                      text-transform:uppercase;margin-bottom:6px;">Radar IA · CX · ATC</div>
          <div style="color:#FF6B5B;font-size:36px;font-family:Georgia,serif;
                      font-style:italic;font-weight:bold;line-height:1;margin-bottom:8px;">GuruSup</div>
          <div style="color:#9CA3AF;font-size:14px;letter-spacing:.03em;">{esc(today)}</div>
        </td>
        <td style="text-align:right;vertical-align:middle;">
          <div style="background:#FF6B5B;color:#fff;font-size:13px;font-weight:700;
                      padding:10px 18px;border-radius:20px;display:inline-block;
                      letter-spacing:.03em;">Lo que no te puedes<br>perder hoy 🔥</div>
        </td>
      </tr>
    </table>
  </div>

  <!-- CARDS -->
  <div style="background:#0F1420;border-radius:0 0 12px 12px;padding:16px 16px 8px;">
    {cards_html}
  </div>

  <!-- FOOTER -->
  <div style="text-align:center;padding:12px 0 4px;font-size:11px;color:#374151;">
    GuruSup Radar IA · generado automáticamente · {esc(today)}
  </div>

</div>
</body>
</html>'''

def take_screenshot(html_content, out="/tmp/radar.png"):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 760, "height": 900}, device_scale_factor=2)
        page.set_content(html_content, wait_until="networkidle")
        page.screenshot(path=out, full_page=True)
        browser.close()
    print(f"  Imagen OK: {out}")

def send_to_discord(image_path):
    with open(image_path, "rb") as f:
        r = requests.post(
            DISCORD_WEBHOOK,
            files={"file": ("radar.png", f, "image/png")},
            data={"payload_json": json.dumps({"content": ""})}
        )
    print("  Discord OK" if r.status_code in (200, 204) else f"  Discord error {r.status_code}: {r.text}")

def main():
    today = format_date_es()
    print(f"GuruSup Radar IA — {today}")
    articles_raw = []
    for cat, medal, query in QUERIES:
        article = fetch_top_article(query)
        if article:
            articles_raw.append((cat, medal, article))
            print(f"  {cat}: {article['title'][:60]}...")
    if not articles_raw:
        print("Sin noticias."); return
    analysis = analyze_with_claude(articles_raw) if ANTHROPIC_KEY else {}
    html_content = generate_html(today, articles_raw, analysis)
    take_screenshot(html_content)
    send_to_discord("/tmp/radar.png")

if __name__ == "__main__":
    main()
