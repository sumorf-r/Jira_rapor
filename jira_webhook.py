#!/usr/bin/env python3
"""Jira -> Telegram real-time webhook receiver.

Jira Cloud, configurable webhook'lar gonderir. Bu Flask servisi:
  POST /jira-webhook  endpoint'ini dinler
  Payload'i parse eder
  Anlamli bir Telegram mesajina cevirir
  Gruba gonderir

Onlemler:
  - Optional shared secret (JIRA_WEBHOOK_SECRET): Jira webhook URL'ine
    ?token=xxx ekleyince eslestirme yapariz; eslesmeyen request'leri red.
  - Health endpoint: GET /health  -> "OK"
  - Tum gelen JSON debug log'a yazilir (/opt/jira_rapor/jira_webhook_debug.log)
  - Telegram gonderimi basarisizsa loglar, exception atmaz (servis devrilmez)

Calistirma:
  python3 jira_webhook.py
  (default port 8089, sadece 127.0.0.1'de dinler — cloudflared aracilik eder)
"""
import os, sys, json, urllib.request, urllib.parse
from datetime import datetime
from flask import Flask, request, jsonify

sys.path.insert(0, "/opt/jira_rapor")
import config as cfg

LOG_FILE   = "/opt/jira_rapor/jira_webhook.log"
DEBUG_FILE = "/opt/jira_rapor/jira_webhook_debug.log"
WEBHOOK_SECRET = getattr(cfg, "JIRA_WEBHOOK_SECRET", None)  # opsiyonel
PORT = 8089

app = Flask(__name__)

def log(msg):
    line = "[" + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "] " + str(msg)
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

def debug_dump(label, data):
    try:
        with open(DEBUG_FILE, "a") as f:
            f.write(f"\n--- {datetime.now().isoformat()}  {label} ---\n")
            f.write(json.dumps(data, ensure_ascii=False, indent=2)[:8000])
            f.write("\n")
    except Exception:
        pass

# ---- Telegram sender ------------------------------------------------------
def tg_send(text):
    try:
        data = urllib.parse.urlencode({
            "chat_id": cfg.TG_CHAT,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{cfg.TG_TOKEN}/sendMessage",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            r = json.loads(resp.read().decode())
            return r.get("ok", False)
    except Exception as e:
        log(f"Telegram HATA: {e}")
        return False

# ---- Helpers --------------------------------------------------------------
def issue_short(issue):
    """{key, summary, type, status, assignee, is_sub, parent_key} dict don."""
    if not issue:
        return None
    f = issue.get("fields", {})
    status = (f.get("status") or {}).get("name", "")
    assignee = (f.get("assignee") or {}).get("displayName", "—") or "—"
    itype = f.get("issuetype") or {}
    type_name = itype.get("name", "")
    parent = f.get("parent") or {}
    parent_key = parent.get("key")
    is_sub = bool(parent_key) or bool(itype.get("subtask"))
    return {
        "key": issue.get("key"),
        "summary": (f.get("summary") or "").strip(),
        "type": type_name,
        "status": status,
        "assignee": assignee,
        "is_sub": is_sub,
        "parent_key": parent_key,
    }

def issue_header(iss):
    """Cok satirli, gorsel hiyerarsik issue basligi.
    Donen: [satir1, satir2, satir3?] -> mesaj icine \n ile birlestirilir"""
    key = iss["key"]
    link = f"<a href=\"{jira_url(key)}\">{html_escape(key)}</a>"
    summary = html_escape(iss["summary"]) if iss.get("summary") else ""

    lines = []
    if iss["is_sub"]:
        lines.append(f"🎫 {link} · <i>Alt görev</i>")
        if iss["parent_key"]:
            parent_link = f"<a href=\"{jira_url(iss['parent_key'])}\">{html_escape(iss['parent_key'])}</a>"
            lines.append(f"📁 Ana görev: {parent_link}")
    else:
        lines.append(f"🎫 {link} · <b>Ana görev</b>")
    if summary:
        lines.append(f"📋 {summary}")
    return "\n".join(lines)

def jira_url(key):
    return f"{cfg.JIRA_BASE}/browse/{key}"

def html_escape(s):
    if not s:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))

def truncate(s, n=120):
    s = (s or "").strip().replace("\n", " ")
    if len(s) > n:
        return s[:n] + "…"
    return s

# ADF (Atlassian Document Format) -> plain text basit cevirici
def adf_to_text(node):
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        parts = []
        for ch in node.get("content", []) or []:
            t = adf_to_text(ch)
            if t:
                parts.append(t)
        sep = "\n" if node.get("type") in ("doc","paragraph","bulletList","listItem","orderedList") else " "
        return sep.join(parts)
    if isinstance(node, list):
        return " ".join(adf_to_text(x) for x in node)
    return ""

# ---- Event formatters -----------------------------------------------------
def fmt_issue_created(payload):
    iss = issue_short(payload.get("issue"))
    if not iss:
        return None
    user = (payload.get("user") or {}).get("displayName", "—")
    return (
        f"🆕  <b>YENİ GÖREV OLUŞTURULDU</b>\n"
        f"\n"
        f"{issue_header(iss)}\n"
        f"📁 Tip: <i>{html_escape(iss['type'])}</i>\n"
        f"🎯 Durum: <i>{html_escape(iss['status'])}</i>\n"
        f"\n"
        f"👤 Atanan: <b>{html_escape(iss['assignee'])}</b>\n"
        f"✏️ Oluşturan: <b>{html_escape(user)}</b>"
    )

def fmt_issue_deleted(payload):
    iss = issue_short(payload.get("issue"))
    if not iss:
        return None
    user = (payload.get("user") or {}).get("displayName", "—")
    sub_tag = " · <i>Alt görev</i>" if iss["is_sub"] else " · <b>Ana görev</b>"
    return (
        f"❌  <b>GÖREV SİLİNDİ</b>\n"
        f"\n"
        f"🎫 {html_escape(iss['key'])}{sub_tag}\n"
        f"📋 {html_escape(iss['summary'])}\n"
        f"\n"
        f"✏️ Silen: <b>{html_escape(user)}</b>"
    )

# Tarih yasak uyarisi sablon basligi/altligi (her iki tarih degisiminde kullanilir)
DATE_BAN_HEADER = (
    "🚫━━━━━━━━━━━━━━━━━━━━━━━━━━━━🚫\n"
    "  ⚠️  <b>TARİH DEĞİŞTİRMEK YASAK</b>  ⚠️\n"
    "🚫━━━━━━━━━━━━━━━━━━━━━━━━━━━━🚫"
)
DATE_BAN_FOOTER = (
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚠️ <i>Tarihler proje planına göre belirlendi.</i>\n"
    "<i>Onaylanmadan tarih değişikliği yapılmamalı.</i>\n"
    "\n"
    "<i>Lütfen tarihi eski haline çeviriniz veya</i>\n"
    "<i>gerekçesini bildiriniz.</i>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
)

# changelog.items[] icindeki bir item'i cumleye cevir
def fmt_change_item(item, iss, user):
    field   = item.get("field", "")
    fieldId = item.get("fieldId", "") or item.get("fieldid", "")
    fromS = item.get("fromString") or "—"
    toS   = item.get("toString")   or "—"

    header = issue_header(iss)

    # ---- STATUS ----
    if field == "status":
        tcat = (toS or "").lower()
        is_done   = "tamam" in tcat or "done" in tcat or "kapal" in tcat
        is_cancel = "iptal" in tcat or "cancel" in tcat
        is_wait   = "bekle" in tcat or "block" in tcat
        is_prog   = "devam" in tcat or "progress" in tcat

        if is_done:
            title = "✅  <b>GÖREV TAMAMLANDI</b>"
            new_label = "<b>✓ " + html_escape(toS) + "</b>"
            footer = "\n\n🎉 <i>Eline sağlık!</i>"
        elif is_cancel:
            title = "❌  <b>GÖREV İPTAL EDİLDİ</b>"
            new_label = "<b>" + html_escape(toS) + "</b>"
            footer = ""
        elif is_wait:
            title = "⏸️  <b>GÖREV BEKLEMEYE ALINDI</b>"
            new_label = "<b>" + html_escape(toS) + "</b>"
            footer = ""
        elif is_prog:
            title = "▶️  <b>GÖREV BAŞLATILDI</b>"
            new_label = "<b>" + html_escape(toS) + "</b>"
            footer = ""
        else:
            title = "🔄  <b>DURUM DEĞİŞTİ</b>"
            new_label = "<b>" + html_escape(toS) + "</b>"
            footer = ""

        return (
            f"{title}\n"
            f"\n"
            f"{header}\n"
            f"\n"
            f"   <i>{html_escape(fromS)}</i>  →  {new_label}\n"
            f"\n"
            f"👤 Atanan: <b>{html_escape(iss['assignee'])}</b>\n"
            f"✏️ Yapan: <b>{html_escape(user)}</b>"
            f"{footer}"
        )

    # ---- ASSIGNEE ----
    if field == "assignee":
        return (
            f"👤  <b>ATANAN DEĞİŞTİ</b>\n"
            f"\n"
            f"{header}\n"
            f"\n"
            f"   <i>{html_escape(fromS)}</i>  →  <b>{html_escape(toS)}</b>\n"
            f"\n"
            f"✏️ Yapan: <b>{html_escape(user)}</b>"
        )

    # ---- TARIH FIELD'leri (bitis + baslangic) ----
    # Iki durum:
    #   a) Ilk kez set ediliyor (eski deger yok)  -> normal bildirim
    #   b) Mevcut tarih degistiriliyor             -> YASAK uyarisi
    raw_from = item.get("fromString")
    raw_to   = item.get("toString")
    has_old  = raw_from not in (None, "", "—")
    has_new  = raw_to   not in (None, "", "—")
    is_first_set = (not has_old) and has_new
    is_real_change = has_old and has_new and (raw_from != raw_to)
    is_cleared   = has_old and (not has_new)

    # ---- DUE DATE (bitis tarihi) ----
    if field == "duedate":
        if is_first_set:
            # Bos alanin doldurulmasi: normal bildirim
            return (
                f"📅  <b>BİTİŞ TARİHİ BELİRLENDİ</b>\n"
                f"\n"
                f"{header}\n"
                f"\n"
                f"   Yeni bitiş tarihi: <b>{html_escape(toS)}</b>\n"
                f"\n"
                f"👤 Atanan: <b>{html_escape(iss['assignee'])}</b>\n"
                f"✏️ Belirleyen: <b>{html_escape(user)}</b>"
            )
        if is_cleared:
            # Tarih kaldirildi: yumusak uyari
            return (
                f"⚠️  <b>BİTİŞ TARİHİ KALDIRILDI</b>\n"
                f"\n"
                f"{header}\n"
                f"\n"
                f"   Eski tarih: <i>{html_escape(fromS)}</i>  →  <b>(temizlendi)</b>\n"
                f"\n"
                f"👤 Atanan: <b>{html_escape(iss['assignee'])}</b>\n"
                f"✏️ Yapan: <b>{html_escape(user)}</b>\n"
                f"\n"
                f"<i>Görev tarihi olmadan takip edilemez. Lütfen yeni tarih giriniz.</i>"
            )
        if is_real_change:
            # Mevcut tarih degistirildi: YASAK
            return (
                f"{DATE_BAN_HEADER}\n"
                f"\n"
                f"📅 <b>BİTİŞ TARİHİ DEĞİŞTİRİLDİ</b>\n"
                f"\n"
                f"{header}\n"
                f"\n"
                f"   ESKİ:  <i>{html_escape(fromS)}</i>\n"
                f"   YENİ:  <b>{html_escape(toS)}</b>  ⚠️\n"
                f"\n"
                f"👤 Atanan: <b>{html_escape(iss['assignee'])}</b>\n"
                f"✏️ Bu işlemi yapan: <b>{html_escape(user)}</b>\n"
                f"\n"
                f"{DATE_BAN_FOOTER}"
            )
        return None  # ayni deger, sessiz

    # ---- START DATE (baslangic tarihi) ----
    is_start_date = (
        fieldId == cfg.JIRA_START_DATE_FIELD
        or fieldId == "customfield_10015"
        or field.lower() in ("start date", "baslangic tarihi", "başlangıç tarihi")
    )
    if is_start_date:
        if is_first_set:
            return (
                f"🚀  <b>BAŞLANGIÇ TARİHİ BELİRLENDİ</b>\n"
                f"\n"
                f"{header}\n"
                f"\n"
                f"   Yeni başlangıç tarihi: <b>{html_escape(toS)}</b>\n"
                f"\n"
                f"👤 Atanan: <b>{html_escape(iss['assignee'])}</b>\n"
                f"✏️ Belirleyen: <b>{html_escape(user)}</b>"
            )
        if is_cleared:
            return (
                f"⚠️  <b>BAŞLANGIÇ TARİHİ KALDIRILDI</b>\n"
                f"\n"
                f"{header}\n"
                f"\n"
                f"   Eski tarih: <i>{html_escape(fromS)}</i>  →  <b>(temizlendi)</b>\n"
                f"\n"
                f"👤 Atanan: <b>{html_escape(iss['assignee'])}</b>\n"
                f"✏️ Yapan: <b>{html_escape(user)}</b>\n"
                f"\n"
                f"<i>Görev tarihi olmadan takip edilemez. Lütfen yeni tarih giriniz.</i>"
            )
        if is_real_change:
            return (
                f"{DATE_BAN_HEADER}\n"
                f"\n"
                f"🚀 <b>BAŞLANGIÇ TARİHİ DEĞİŞTİRİLDİ</b>\n"
                f"\n"
                f"{header}\n"
                f"\n"
                f"   ESKİ:  <i>{html_escape(fromS)}</i>\n"
                f"   YENİ:  <b>{html_escape(toS)}</b>  ⚠️\n"
                f"\n"
                f"👤 Atanan: <b>{html_escape(iss['assignee'])}</b>\n"
                f"✏️ Bu işlemi yapan: <b>{html_escape(user)}</b>\n"
                f"\n"
                f"{DATE_BAN_FOOTER}"
            )
        return None  # ayni deger, sessiz

    # ---- PRIORITY ----
    if field == "priority":
        return (
            f"⚡  <b>ÖNCELİK DEĞİŞTİ</b>\n"
            f"\n"
            f"{header}\n"
            f"\n"
            f"   <i>{html_escape(fromS)}</i>  →  <b>{html_escape(toS)}</b>\n"
            f"\n"
            f"✏️ Yapan: <b>{html_escape(user)}</b>"
        )

    # ---- SUMMARY (baslik) ----
    if field == "summary":
        return (
            f"✏️  <b>BAŞLIK DEĞİŞTİ</b>\n"
            f"\n"
            f"🎫 <a href=\"{jira_url(iss['key'])}\">{html_escape(iss['key'])}</a>"
            f"{' · <i>Alt görev</i>' if iss['is_sub'] else ' · <b>Ana görev</b>'}\n"
            f"\n"
            f"   ESKİ: <i>{truncate(html_escape(fromS), 80)}</i>\n"
            f"   YENİ: <b>{truncate(html_escape(toS), 80)}</b>\n"
            f"\n"
            f"✏️ Yapan: <b>{html_escape(user)}</b>"
        )

    # ---- LABELS ----
    if field == "labels":
        return (
            f"🏷️  <b>ETİKET DEĞİŞTİ</b>\n"
            f"\n"
            f"{header}\n"
            f"\n"
            f"   <i>{html_escape(fromS) or '(boş)'}</i>  →  <b>{html_escape(toS) or '(boş)'}</b>\n"
            f"\n"
            f"✏️ Yapan: <b>{html_escape(user)}</b>"
        )

    # ---- PARENT (alt gorev parent'i degistirildi) ----
    if field in ("Parent", "parent"):
        return (
            f"🔗  <b>ANA GÖREV (parent) DEĞİŞTİ</b>\n"
            f"\n"
            f"{header}\n"
            f"\n"
            f"   <i>{html_escape(fromS)}</i>  →  <b>{html_escape(toS)}</b>\n"
            f"\n"
            f"✏️ Yapan: <b>{html_escape(user)}</b>"
        )

    # Diger field'lar -> sessiz (worklog, time tracking, vb. spam yapma)
    return None

def fmt_issue_updated(payload):
    iss = issue_short(payload.get("issue"))
    if not iss:
        return None
    user = (payload.get("user") or {}).get("displayName", "—")
    cl = payload.get("changelog") or {}
    items = cl.get("items") or []

    msgs = []
    for item in items:
        m = fmt_change_item(item, iss, user)
        if m:
            msgs.append(m)
    if not msgs:
        return None
    # Birden fazla degisiklik varsa ardarda tek mesajda gonder (ayrac)
    return "\n\n".join(msgs)

def fmt_comment_created(payload):
    # comment_created event'inde issue ve comment ayri payload'da gelir
    iss = issue_short(payload.get("issue"))
    cm = payload.get("comment") or {}
    if not iss:
        return None
    author = ((cm.get("author") or {}).get("displayName")
              or (cm.get("updateAuthor") or {}).get("displayName") or "—")
    body = cm.get("body")
    if isinstance(body, dict):
        body_text = adf_to_text(body)
    else:
        body_text = str(body or "")
    body_text = truncate(body_text, 200)
    return (
        f"💬  <b>YENİ YORUM</b>\n"
        f"\n"
        f"{issue_header(iss)}\n"
        f"\n"
        f"👤 <b>{html_escape(author)}</b> yazdı:\n"
        f"<i>\"{html_escape(body_text)}\"</i>"
    )

# ---- Routes ---------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

@app.route("/jira-webhook", methods=["POST"])
def jira_webhook():
    # Optional secret check
    if WEBHOOK_SECRET:
        if request.args.get("token") != WEBHOOK_SECRET:
            log(f"REJECTED (bad token) from {request.remote_addr}")
            return jsonify({"error": "forbidden"}), 403

    try:
        payload = request.get_json(force=True, silent=True) or {}
    except Exception as e:
        log(f"JSON parse hata: {e}")
        return jsonify({"error": "bad json"}), 400

    event = payload.get("webhookEvent", "unknown")
    issue_event = payload.get("issue_event_type_name", "")
    debug_dump(f"{event} / {issue_event}", payload)
    log(f"Event: {event}  /  {issue_event}")

    # ---- PROJE WHITELIST FILTRESI -----------------------------------------
    # Sadece config.PROJECTS'te olan projelerin event'lerini isle.
    # Issue key'inden proje kodunu cikar (ornek: "GNDFAB-100" -> "GNDFAB")
    issue = payload.get("issue") or {}
    issue_key = issue.get("key") or ""
    proj_code = issue_key.split("-")[0] if "-" in issue_key else ""
    allowed_projects = set(cfg.PROJECTS)
    if proj_code and proj_code not in allowed_projects:
        log(f"  -> Atlandi: {issue_key} ({proj_code} whitelist'te yok)")
        return jsonify({"sent": False, "reason": "project_not_in_whitelist",
                        "project": proj_code}), 200

    # Event router
    msg = None
    if event == "jira:issue_created":
        msg = fmt_issue_created(payload)
    elif event == "jira:issue_deleted":
        msg = fmt_issue_deleted(payload)
    elif event == "jira:issue_updated":
        msg = fmt_issue_updated(payload)
    elif event == "comment_created":
        msg = fmt_comment_created(payload)
    elif event == "comment_updated":
        m = fmt_comment_created(payload)
        if m:
            msg = m.replace("💬  <b>YENİ YORUM</b>", "✏️  <b>YORUM GÜNCELLENDİ</b>")
    # diger event'leri sessizce gec (worklog vs)

    if msg:
        ok = tg_send(msg)
        log(f"  -> Telegram: {'OK' if ok else 'FAIL'}")
        return jsonify({"sent": ok}), 200
    else:
        return jsonify({"sent": False, "reason": "no_match"}), 200

# ---- Main -----------------------------------------------------------------
if __name__ == "__main__":
    log(f"=== jira_webhook server basliyor (port {PORT}) ===")
    if WEBHOOK_SECRET:
        log("  Secret: AKTIF (URL'e ?token=... ekleyin)")
    else:
        log("  Secret: KAPALI (test icin OK, prod icin config.py'ye JIRA_WEBHOOK_SECRET ekle)")
    # Sadece 127.0.0.1'de dinle (cloudflared lokalden baglanir)
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
