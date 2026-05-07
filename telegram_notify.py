#!/usr/bin/env python3
"""Jira'dan yaklasan/geciken gorevleri cekip Telegram grubuna uyari gonderir."""
import urllib.request, urllib.parse, base64, json, random, sys, os
from datetime import date, datetime
from collections import defaultdict

# ---- KONFIG (config.py'den) -----------------------------------------------
import sys as _sys
_sys.path.insert(0, "/opt/jira_rapor")
import config as _cfg
JIRA_TOKEN = _cfg.JIRA_TOKEN
JIRA_EMAIL = _cfg.JIRA_EMAIL
JIRA_BASE  = _cfg.JIRA_BASE
TG_TOKEN   = _cfg.TG_TOKEN
TG_CHAT    = _cfg.TG_CHAT
PROJECTS   = _cfg.PROJECTS
LOG_FILE = "/opt/jira_rapor/telegram.log"

# ---- HELPERS --------------------------------------------------------------
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

def fetch_issues(project_key):
    creds = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()
    headers = {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = json.dumps({
        "jql": f"project={project_key} AND statusCategory != Done ORDER BY duedate ASC",
        "maxResults": 500,
        "fields": ["summary", "status", "assignee", "duedate", "issuetype"]
    }).encode()
    req = urllib.request.Request(
        f"{JIRA_BASE}/rest/api/3/search/jql",
        data=payload, headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("issues", [])

def first_name(full):
    if not full:
        return None
    return full.strip().split()[0]

def days_left(due_str):
    if not due_str:
        return None
    try:
        d = date.fromisoformat(due_str[:10])
        return (d - date.today()).days
    except Exception:
        return None

# ---- MESAJ SABLONLARI -----------------------------------------------------
COMMENTS_OVERDUE = [
    "tarih gecmis, kafani kaldir",
    "geciken her gun bir hayalet, bugun bitirelim",
    "bu is bekledikce kalitesini kaybediyor",
    "ekrandaki kirmizi yazi seni cagiriyor",
    "yarin sabah toplantiya birlikte gelmesin"
]
COMMENTS_TODAY = [
    "BUGUN son gun, mesai sende",
    "saat geciyor, klavyenin basina",
    "bugun bitmezse yarin acemi onbasi olursun",
    "moralim sende, bitir su isi"
]
COMMENTS_TOMORROW = [
    "yarin son gun, sabaha birakma",
    "uyumadan once bir bakistir",
    "yarinki sabah kahvenin tadi sana bagli"
]
COMMENTS_3DAYS = [
    "az kaldi, ipi gogusle",
    "3 gun sonra herkes bunu sormaya baslayacak",
    "bu hafta seninle iftihar etmek istiyoruz"
]
COMMENTS_WEEK = [
    "ajandaya yaz, aklinda bulunsun",
    "bu hafta seni bekliyor",
    "rahatsana ama unutma"
]

def pick(arr):
    return random.choice(arr)

def emoji_for(days):
    if days is None:       return "⚪"
    if days < 0:           return "💀"
    if days == 0:          return "🔥"
    if days == 1:          return "🚨"
    if days <= 3:          return "🟠"
    if days <= 7:          return "🟡"
    return "🟢"

# ---- ANA --------------------------------------------------------------
def main():
    log("=== Telegram bildirim gorevi basladi ===")

    # 1) Tum aktif gorevleri cek
    all_issues = []
    for proj in PROJECTS:
        try:
            issues = fetch_issues(proj)
            log(f"{proj}: {len(issues)} aktif gorev")
            for i in issues:
                f = i["fields"]
                d = days_left(f.get("duedate"))
                if d is None:
                    continue  # tarihsiz olanlari es gec
                if d > 3:
                    continue  # sadece 3 gun ve aciligi yuksek olanlar
                # Alt gorev de olsa kabul ediyoruz
                all_issues.append({
                    "key":    i["key"],
                    "summary": f["summary"],
                    "status":  f["status"]["name"],
                    "assignee": (f.get("assignee") or {}).get("displayName"),
                    "days":     d
                })
        except Exception as e:
            log(f"HATA ({proj}): {e}")

    if not all_issues:
        log("Yaklasan gorev yok, mesaj gonderilmedi")
        return

    # 2) Acilik seviyesine gore gruplandir
    groups = defaultdict(list)
    for it in sorted(all_issues, key=lambda x: x["days"]):
        d = it["days"]
        if d < 0:    bucket = "overdue"
        elif d == 0: bucket = "today"
        elif d == 1: bucket = "tomorrow"
        elif d <= 3: bucket = "3days"
        else:        bucket = "week"
        groups[bucket].append(it)

    # 3) Mesaji olustur (HTML format)
    def esc(s):
        if s is None: return ""
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    import sys as _sys
    _sys.path.insert(0, "/opt/jira_rapor")
    import tg_helper
    tg_helper.delete_previous()
    send = tg_helper.send

    today_str = date.today().strftime("%d.%m.%Y")
    total = len(all_issues)

    # Baslik mesaji
    send(f"🗓 <b>GUNLUK GOREV TAKIBI — {today_str}</b>\n<i>Toplam {total} acil gorev (≤3 gun veya gecikmis)</i>")

    SECTIONS = [
        ("overdue",  "💀 <b>SURESI GECMIS</b>"),
        ("today",    "🔥 <b>BUGUN SON GUN</b>"),
        ("tomorrow", "🚨 <b>YARIN SON GUN</b>"),
        ("3days",    "🟠 <b>3 GUN ICINDE</b>"),
    ]

    sent_count = 0
    for key, header in SECTIONS:
        items = groups.get(key, [])
        if not items:
            continue

        # Her kategori icin parca parca gonder (4096 limit)
        chunks = [[header]]
        cur_len = len(header)
        for it in items:
            name = first_name(it["assignee"]) or "(boshta)"
            d = it["days"]
            if d < 0:    sure = f"{abs(d)} GUN GECTI"
            elif d == 0: sure = "BUGUN!"
            elif d == 1: sure = "1 GUN"
            else:        sure = f"{d} gun"
            line1 = f"  {emoji_for(d)} <code>{esc(it['key'])}</code> — <b>{esc(name)}</b> ({sure})"
            line2 = f"     › {esc(it['summary'])}"
            block = line1 + "\n" + line2
            if cur_len + len(block) + 2 > 3800:
                chunks.append([f"{header} <i>(devam)</i>"])
                cur_len = len(header) + 12
            chunks[-1].append(block)
            cur_len += len(block) + 2

        for ch in chunks:
            if send("\n".join(ch)):
                sent_count += 1

    log(f"{sent_count} mesaj gonderildi ({total} gorev)")

    log("=== Gorev tamamlandi ===")

if __name__ == "__main__":
    main()
