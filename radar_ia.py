#!/usr/bin/env python3
import feedparser, requests, json, html, os, re, smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SMTP_HOST     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ["SMTP_USER"]
SMTP_PASS     = os.environ["SMTP_PASS"]
EMAIL_TO      = os.environ["EMAIL_TO"]  # separados por coma si son varios

DAYS_ES   = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
MONTHS_ES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto",
             "septiembre","octubre","noviembre","diciembre"]

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
            return {
                "title": title,
                "link": e.link,
                "source": e.get("source", {}).get("title", "Google News"),
                "summary": summary,
            }
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
        prompt = f"""Eres el analista de GuruSup (startup española de AI agents para customer support,
compite con Decagon, Sierra, Ada, Intercom Fin; ICP: startups B2C Series A-C España/LATAM 5k-50k tickets/mes).
Genera el resumen diario EN ESPAÑOL. Responde ÚNICAMENTE con este JSON exacto sin texto adicional:
{{"SECTOR":{{"title":"titular potente en español máx 90 chars","paragraph":"2-3 frases, qué pasó y por qué importa, máx 4 líneas","kpis":["dato numérico impactante con contexto","dato numérico impactante con contexto","dato numérico impactante con contexto"],"recommendation":"1-2 frases: por qué le interesa a GuruSup y qué oportunidad/acción concreta tiene"}},"COMPETENCIA":{{"title":"...","paragraph":"...","kpis":["...","...","..."],"recommendation":"..."}},"TENDENCIAS":{{"title":"...","paragraph":"...","kpis":["...","...","..."],"recommendation":"..."}}}}
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

def generate_email_html(today, articles_raw, analysis):
    MEDALS = {"SECTOR": "🥇", "COMPETENCIA": "🥈", "TENDENCIAS": "🥉"}

    blocks = ""
    for cat, _, article in articles_raw:
        a     = analysis.get(cat, {})
        title = esc(a.get("title") or article["title"])
        para  = esc(a.get("paragraph") or article["summary"][:400])
        kpis  = a.get("kpis") or []
        rec   = esc(a.get("recommendation") or "")
        src   = esc(article["source"])
        link  = article["link"]
        medal = MEDALS[cat]

        kpi_rows = "".join(
            f"""<tr>
              <td width="14" style="padding:4px 0;vertical-align:top;color:#FF6B5B;font-weight:700;font-size:14px;">&#x25CF;</td>
              <td style="padding:4px 0;font-size:14px;color:#D1D5DB;line-height:1.55;font-family:Arial,sans-serif;">{esc(k)}</td>
            </tr>"""
            for k in kpis
        )

        rec_block = ""
        if rec:
            rec_block = f"""
            <tr><td colspan="2">
              <div style="border-top:1px solid #2D3748;margin:14px 0 12px;"></div>
              <p style="margin:0;font-size:13px;color:#9CA3AF;line-height:1.65;font-family:Arial,sans-serif;">
                &#x1F4A1;&nbsp;<strong style="color:#E5E7EB;">Por qué le interesa a GuruSup:</strong><br>
                <span style="color:#CBD5E0;">{rec}</span>
              </p>
            </td></tr>"""

        blocks += f"""
        <!-- BLOQUE {cat} -->
        <tr><td style="padding:0 0 16px 0;">
          <table cellpadding="0" cellspacing="0" width="100%" style="background:#161B27;border-radius:10px;border-left:4px solid #FF6B5B;overflow:hidden;">
            <tr><td style="padding:18px 20px 16px 20px;">
              <!-- Categoría -->
              <p style="margin:0 0 10px 0;">
                <span style="display:inline-block;background:#0D1117;color:#FF6B5B;font-size:11px;font-weight:800;
                             padding:4px 10px;border-radius:4px;letter-spacing:.1em;text-transform:uppercase;
                             border:1px solid #FF6B5B;font-family:Arial,sans-serif;">{medal} {cat}</span>
              </p>
              <!-- Titular -->
              <p style="margin:0 0 8px 0;font-family:Georgia,serif;font-size:19px;font-weight:bold;
                        color:#F9FAFB;line-height:1.35;">{title}</p>
              <!-- Fuente -->
              <p style="margin:0 0 12px 0;font-size:12px;color:#6B7280;font-family:Arial,sans-serif;">
                &#x1F4F0;&nbsp;Fuente:&nbsp;<a href="{link}" style="color:#9CA3AF;text-decoration:none;">{src}</a>
              </p>
              <!-- Descripción -->
              <p style="margin:0 0 14px 0;font-size:14px;color:#9CA3AF;line-height:1.65;font-family:Arial,sans-serif;">{para}</p>
              <!-- KPIs -->
              <table cellpadding="0" cellspacing="0" width="100%">
                {kpi_rows}
                {rec_block}
              </table>
            </td></tr>
          </table>
        </td></tr>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>GuruSup Radar IA — {esc(today)}</title>
</head>
<body style="margin:0;padding:0;background:#0A0E1A;">
<table cellpadding="0" cellspacing="0" width="100%" style="background:#0A0E1A;">
<tr><td align="center" style="padding:24px 16px;">

  <table cellpadding="0" cellspacing="0" width="660" style="max-width:660px;">

    <!-- BANNER -->
    <tr><td style="background:#0D1117;border-radius:12px 12px 0 0;padding:28px 30px 22px;
                   border-bottom:2px solid #FF6B5B;">
      <table cellpadding="0" cellspacing="0" width="100%"><tr>
        <td>
          <p style="margin:0 0 6px 0;color:#6B7280;font-size:11px;font-weight:600;
                    letter-spacing:.15em;text-transform:uppercase;font-family:Arial,sans-serif;">Radar IA · CX · ATC</p>
          <p style="margin:0 0 8px 0;color:#FF6B5B;font-size:36px;font-family:Georgia,serif;
                    font-style:italic;font-weight:bold;line-height:1;">GuruSup</p>
          <p style="margin:0;color:#9CA3AF;font-size:14px;font-family:Arial,sans-serif;">{esc(today)}</p>
        </td>
        <td align="right" valign="middle">
          <span style="display:inline-block;background:#FF6B5B;color:#ffffff;font-size:13px;
                       font-weight:700;padding:10px 18px;border-radius:20px;font-family:Arial,sans-serif;
                       line-height:1.4;text-align:center;">Lo que no te<br>puedes perder hoy &#x1F525;</span>
        </td>
      </tr></table>
    </td></tr>

    <!-- CONTENIDO -->
    <tr><td style="background:#0F1420;border-radius:0 0 12px 12px;padding:16px 16px 8px;">
      <table cellpadding="0" cellspacing="0" width="100%">
        {blocks}
      </table>
    </td></tr>

    <!-- FOOTER -->
    <tr><td style="padding:12px 0 4px;text-align:center;font-size:11px;
                   color:#374151;font-family:Arial,sans-serif;">
      GuruSup Radar IA &middot; generado automáticamente &middot; {esc(today)}
    </td></tr>

  </table>
</td></tr>
</table>
</body>
</html>"""

def send_email(subject, html_content, today):
    recipients = [r.strip() for r in EMAIL_TO.split(",")]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"GuruSup Radar IA <{SMTP_USER}>"
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, recipients, msg.as_string())
    print(f"  Email OK → {EMAIL_TO}")

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

    analysis     = analyze_with_claude(articles_raw) if ANTHROPIC_KEY else {}
    html_content = generate_email_html(today, articles_raw, analysis)

    # Asunto: titular de la noticia más relevante del día (SECTOR)
    sector_title = analysis.get("SECTOR", {}).get("title") or articles_raw[0][2]["title"]
    subject = f"🔎 Radar IA {today[:2].lower()}. {today.split(',')[1].strip()} — {sector_title[:60]}"

    send_email(subject, html_content, today)

if __name__ == "__main__":
    main()
