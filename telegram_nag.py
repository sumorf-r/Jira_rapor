#!/usr/bin/env python3
"""Saatlik uyuz mudur modu — geciken/bugun/yarin biten gorevleri tek tek dirter."""
import urllib.request, urllib.parse, urllib.error, base64, json, random, sys, time
from datetime import date, datetime

import sys as _sys
_sys.path.insert(0, "/opt/jira_rapor")
import config as _cfg
JIRA_TOKEN = _cfg.JIRA_TOKEN
JIRA_EMAIL = _cfg.JIRA_EMAIL
JIRA_BASE  = _cfg.JIRA_BASE
TG_TOKEN   = _cfg.TG_TOKEN
TG_CHAT    = _cfg.TG_CHAT
PROJECTS   = list(_cfg.PROJECTS)
LOG_FILE = "/opt/jira_rapor/telegram_nag.log"

# ---- UYUZ MUDUR LAFLARI ---------------------------------------------------
NAG_OVERDUE = [
    "{name}, {key} hala acik. Sabah da konusmustuk degil mi?",
    "{name} bey/hanim, {key}. Bekliyoruz, kibarca soyluyorum.",
    "{name}, {key} - bu kacinci hatirlatma sayiyor musun?",
    "{name}, {key} tarihi gecti. Insan utanmasa unutmus diyecek.",
    "{name} kardesim, {key}. Bana bakmayi birak, ekrani ac.",
    "{name}, {key}. Sabredemiyorum artik, samimi soyluyorum.",
    "{name}, {key}. Bu satirlari severek yazmiyorum.",
    "{name} usta, {key}. Misafir gibi geldin gibi geldin.",
    "{name}, {key}. Toplantida konusulacak konu listeme ekledim.",
    "{name}, {key}. Sirket icinde konusuluyor, duyurmayayim.",
    "{name}, {key}. Bu mesaj 14. olur, sayiyorum.",
    "{name}, {key} - tarihler asilan limitlerin neydi?",
    "{name}, {key}. Aklima geldikce ictim, sen de bil.",
    "{name}, {key}. Yoneticim sordugunda 'bilmiyorum' demiyeceksin demi?",
    "{name}, {key}. Saat saat bakiyorum, hareket yok.",
    "{name}, {key}. Bu bir hatirlatma da degil artik, ihbar.",
    "{name}, {key}. Iki dakikani ayir, gerekirse kahveni getireyim.",
    "{name}, {key}. Hatirlatmaya devam mi, yoksa bitiyor mu?",
    "{name}, {key}. Senden umutluydum, hala umutluyum ama az kaldi.",
    "{name}, {key}. Iki kelime yazsan da bilelim ne durumda?"
]
NAG_TODAY = [
    "{name}, {key} BUGUN bitmesi gerekiyor. Hatirlatmis olayim.",
    "{name}, {key} - bugunun gozdesi sensin.",
    "{name}, {key}. Aksam cikarken 'kapadim' diyebilelim.",
    "{name}, {key} bugun. Cay molasi sonrasi ilk is olabilir.",
    "{name}, {key}. Saat geciyor, ben de geciyor sanki seninle.",
    "{name}, {key}. Bugun bitmezse yarin daha cok konusuruz.",
    "{name}, {key} - son gun sendrome girmedim demeyesin.",
    "{name}, {key}. Bugun. BUGUN. Daha net nasil yazabilirim?",
    "{name} bey/hanim, {key}. Bugune yetistirmemiz gerekiyor.",
    "{name}, {key}. Saat 17.30'da seninle goz goze gelmeyelim."
]
NAG_TOMORROW = [
    "{name}, {key} yarin son gun. Bugunden hazirlik faydali olur.",
    "{name}, {key}. Yarinki son gun, planini soyle bir gozden gecir.",
    "{name}, {key} yarin. Akilda bulunsun, bana sora sora yapma.",
    "{name}, {key}. Yarinki ajandan dolu mu? Bunu sigdir.",
    "{name}, {key} - 1 gun var. Bilesin diye yaziyorum.",
    "{name}, {key}. Yarin son gun, simdiden dokunsan iyi olur.",
    "{name}, {key}. Sabah ilk is bu olsun bence."
]

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except: pass

def fetch(project_key):
    creds = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()
    headers = {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json", "Accept": "application/json"
    }
    payload = json.dumps({
        "jql": f"project={project_key} AND statusCategory != Done AND duedate <= 2d ORDER BY duedate ASC",
        "maxResults": 200,
        "fields": ["summary", "status", "assignee", "duedate"]
    }).encode()
    req = urllib.request.Request(f"{JIRA_BASE}/rest/api/3/search/jql",
                                 data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("issues", [])

def first_name(full):
    return full.strip().split()[0] if full else "(boshta olan kisi)"

def days_left(due_str):
    if not due_str: return None
    try:
        return (date.fromisoformat(due_str[:10]) - date.today()).days
    except: return None

def esc(s):
    return ("" if s is None else str(s)).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

sys.path.insert(0, "/opt/jira_rapor")
import tg_helper
send = tg_helper.send

def main():
    log("=== Saatlik nag basladi ===")
    tg_helper.delete_previous()

    # Toplam saatlik mesaj limiti (spam olmasin)
    MAX_MESSAGES = 15

    candidates = []
    for proj in PROJECTS:
        try:
            for i in fetch(proj):
                f = i["fields"]
                d = days_left(f.get("duedate"))
                if d is None: continue
                if d > 1: continue  # sadece overdue + bugun + yarin
                candidates.append({
                    "key":      i["key"],
                    "summary":  f["summary"],
                    "assignee": (f.get("assignee") or {}).get("displayName"),
                    "days":     d
                })
        except Exception as e:
            log(f"  Jira hatasi ({proj}): {e}")

    if not candidates:
        log("Yaklasan/geciken gorev yok, sessizlik")
        return

    # Aciliga gore sirala
    candidates.sort(key=lambda x: x["days"])
    log(f"{len(candidates)} aday gorev bulundu, max {MAX_MESSAGES} mesaj gonderilecek")

    sent = 0
    for it in candidates[:MAX_MESSAGES]:
        d = it["days"]
        name = first_name(it["assignee"])
        if d < 0:
            sure = f"{abs(d)} GUN GECTI"
            emoji = "💀"
        elif d == 0:
            sure = "BUGUN SON GUN"
            emoji = "🔥"
        else:
            sure = "YARIN SON GUN"
            emoji = "🚨"

        msg = (f"{emoji} <code>{esc(it['key'])}</code> — <b>{esc(name)}</b> ({sure})\n"
               f"     › {esc(it['summary'])}")

        if send(msg):
            sent += 1
            time.sleep(0.5)

    log(f"{sent} uyuz mesaj gonderildi")
    log("=== Bitti ===")

if __name__ == "__main__":
    main()
