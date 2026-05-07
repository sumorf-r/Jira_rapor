#!/usr/bin/env python3
"""Telegram Gorsel Dashboard.

Cikti: Tek PNG icinde:
  - Header bar (proje sayilari + tarih)
  - 4 donut chart (her proje icin durum dagilimi)
  - Bar chart: Aktif gorevler durum bazli
  - "ACIL GOREVLER" listesi (geciken/bugun/yarin biten)
  - Footer

Telegram'a sendPhoto ile gonderilir.

Kullanim (manuel):
    python3 telegram_visual.py             # tum gruba gonder
    python3 telegram_visual.py --test      # sadece kayitli test alicisina

Cron icin: cron_runner ile sarmal.
"""
import os, sys, json, base64, urllib.request, urllib.parse
from datetime import date, datetime, timedelta
from io import BytesIO

sys.path.insert(0, "/opt/jira_rapor")
import config as cfg

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.gridspec import GridSpec

LOG_FILE = "/opt/jira_rapor/telegram_visual.log"
TODAY = date.today()

# Test modu: --test argumaniyla sadece bu chat_id'ye gonder
# (kendi userId'in: bot ile özel mesajlasmaya basladiktan sonra getUpdates ile alinir)
TEST_CHAT = None  # ileride doldurulabilir; simdilik test --> grup

# ---- Logger ---------------------------------------------------------------
def log(msg):
    line = "[" + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "] " + str(msg)
    print(line)
    with open(LOG_FILE, "a") as lf:
        lf.write(line + "\n")

# ---- Jira fetch -----------------------------------------------------------
_creds = base64.b64encode(f"{cfg.JIRA_EMAIL}:{cfg.JIRA_TOKEN}".encode()).decode()
_h = {"Authorization": f"Basic {_creds}",
      "Content-Type": "application/json", "Accept": "application/json"}

def fetch_all(project_key):
    fields = ["summary", "status", "assignee", "priority", "issuetype",
              "duedate", cfg.JIRA_START_DATE_FIELD, "parent"]
    issues = []
    next_token = None
    while True:
        body = {"jql": f"project={project_key} ORDER BY key ASC",
                "maxResults": 500, "fields": fields}
        if next_token:
            body["nextPageToken"] = next_token
        req = urllib.request.Request(
            f"{cfg.JIRA_BASE}/rest/api/3/search/jql",
            data=json.dumps(body).encode(), headers=_h, method="POST")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
        issues.extend(data.get("issues", []))
        if data.get("isLast", True):
            break
        next_token = data.get("nextPageToken")
        if not next_token:
            break
    return issues

def parse_d(s):
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None

# ---- Veri toplama --------------------------------------------------------
def gather_stats():
    """Donen yapı:
    {
        "projects": {
            "RPA": {"total": 50, "done": 12, "in_progress": 8, "todo": 28, "blocked": 2, "overdue": 5, "today": 1, "tomorrow": 2},
            ...
        },
        "urgent": [
            {"key":"GNDFAB-3", "summary":"...", "assignee":"X", "due_label":"BUGUN!", "color":"FF6600", "proj":"GNDFAB"},
            ...
        ]
    }
    """
    result = {"projects": {}, "urgent": []}

    for proj in cfg.PROJECTS:
        log(f"  {proj} cekiliyor...")
        issues = fetch_all(proj)
        stats = {"total": 0, "done": 0, "in_progress": 0, "todo": 0,
                 "blocked": 0, "overdue": 0, "today": 0, "tomorrow": 0}
        for iss in issues:
            f = iss["fields"]
            stats["total"] += 1
            cat = (f["status"].get("statusCategory") or {}).get("key", "")
            name = f["status"]["name"]
            due = parse_d(f.get("duedate"))

            if cat == "done":
                stats["done"] += 1
            elif name == "Beklemede":
                stats["blocked"] += 1
            elif cat == "indeterminate":
                stats["in_progress"] += 1
            else:
                stats["todo"] += 1

            # Aciliyet (sadece done degilse)
            if cat != "done" and due:
                if due < TODAY:
                    stats["overdue"] += 1
                    label, color = f"GECTI ({(TODAY-due).days}g)", "#C0392B"
                elif due == TODAY:
                    stats["today"] += 1
                    label, color = "BUGUN", "#E67E22"
                elif due == TODAY + timedelta(days=1):
                    stats["tomorrow"] += 1
                    label, color = "YARIN", "#F39C12"
                else:
                    label, color = None, None

                if label:
                    result["urgent"].append({
                        "key": iss["key"],
                        "summary": f["summary"][:55],
                        "assignee": (f.get("assignee") or {}).get("displayName", "—") or "—",
                        "due_label": label, "color": color, "proj": proj,
                        "due": due,
                    })
        result["projects"][proj] = stats

    # Urgent listesini sirala: once geciken (eski ilk), sonra bugun, sonra yarin
    result["urgent"].sort(key=lambda x: (x["due"], x["proj"], x["key"]))
    return result

# ---- Gorsel uretimi ------------------------------------------------------
TR_MONTHS = ["Ocak","Subat","Mart","Nisan","Mayis","Haziran",
             "Temmuz","Agustos","Eylul","Ekim","Kasim","Aralik"]
TR_DAYS   = ["Pazartesi","Sali","Carsamba","Persembe","Cuma","Cumartesi","Pazar"]

def make_dashboard(stats):
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.edgecolor": "#CCCCCC",
        "axes.labelcolor": "#2C3E50",
        "xtick.color": "#5A6A85",
        "ytick.color": "#5A6A85",
    })

    # Toplam aktif
    total_active = sum(p["total"] - p["done"] for p in stats["projects"].values())
    total_overdue = sum(p["overdue"] for p in stats["projects"].values())
    total_today = sum(p["today"] for p in stats["projects"].values())
    total_tomorrow = sum(p["tomorrow"] for p in stats["projects"].values())
    total_done_today = 0  # cana ait olanlari ileride ekleriz

    # Layout: 5 satir (header / kpi / projeler / bar / urgent / footer)
    fig = plt.figure(figsize=(12, 14), facecolor="#F7F9FC")
    gs = GridSpec(6, 4, figure=fig,
                  height_ratios=[0.7, 0.6, 2.8, 1.8, 3.2, 0.3],
                  hspace=0.7, wspace=0.3,
                  left=0.04, right=0.96, top=0.97, bottom=0.02)

    # ── HEADER ──
    ax_h = fig.add_subplot(gs[0, :])
    ax_h.set_xlim(0, 1); ax_h.set_ylim(0, 1)
    ax_h.axis("off")
    # mavi banner
    ax_h.add_patch(FancyBboxPatch((0, 0.05), 1, 0.9,
        boxstyle="round,pad=0.01,rounding_size=0.02",
        linewidth=0, facecolor="#1B3A6B"))
    ax_h.text(0.02, 0.65, "GÜNDOĞDU DAIRY INDUSTRY",
        fontsize=22, fontweight="bold", color="white", va="center")
    ax_h.text(0.02, 0.30,
        f"Dijital Dönüşüm — {TODAY.day:02d} {TR_MONTHS[TODAY.month-1]} {TODAY.year}, {TR_DAYS[TODAY.weekday()]}",
        fontsize=12, color="#A8C4E8", va="center")
    ax_h.text(0.98, 0.50, datetime.now().strftime("%H:%M"),
        fontsize=20, fontweight="bold", color="white", va="center", ha="right")

    # ── KPI bar ──
    ax_k = fig.add_subplot(gs[1, :])
    ax_k.axis("off"); ax_k.set_xlim(0, 4); ax_k.set_ylim(0, 1)
    kpis = [
        (f"{total_active}", "AKTİF GÖREV", "#2980B9"),
        (f"{total_overdue}", "SÜRESİ GEÇMİŞ", "#C0392B"),
        (f"{total_today}", "BUGÜN BİTİYOR", "#E67E22"),
        (f"{total_tomorrow}", "YARIN BİTİYOR", "#F39C12"),
    ]
    for i, (val, label, color) in enumerate(kpis):
        ax_k.add_patch(FancyBboxPatch((i + 0.05, 0.05), 0.9, 0.9,
            boxstyle="round,pad=0.005,rounding_size=0.05",
            linewidth=2, edgecolor=color, facecolor="white"))
        ax_k.text(i + 0.5, 0.65, val, fontsize=26, fontweight="bold",
                  color=color, ha="center", va="center")
        ax_k.text(i + 0.5, 0.20, label, fontsize=9, fontweight="bold",
                  color="#5A6A85", ha="center", va="center")

    # ── 4 Donut (her proje) ──
    proj_codes = list(stats["projects"].keys())
    for i, proj in enumerate(proj_codes[:4]):
        ax = fig.add_subplot(gs[2, i])
        s = stats["projects"][proj]
        sizes  = [s["done"], s["in_progress"], s["todo"], s["blocked"]]
        labels = ["Tamam", "Devam", "Yapılacak", "Bekleme"]
        clrs   = ["#27AE60", "#2980B9", "#95A5A6", "#E67E22"]
        # 0 olanlari kaldirma — ama legend icin 0 olsa da goster
        nonzero = [(z, l, c) for z, l, c in zip(sizes, labels, clrs) if z > 0]
        if nonzero:
            zsizes, zlabs, zclrs = zip(*nonzero)
            ax.pie(zsizes, labels=None, colors=zclrs,
                   wedgeprops=dict(width=0.30, edgecolor="white", linewidth=2),
                   startangle=90)
        # Merkez sayisi
        pct = round(100 * s["done"] / s["total"]) if s["total"] else 0
        ax.text(0, 0.05, f"{pct}%", fontsize=22, fontweight="bold",
                color="#1B3A6B", ha="center", va="center")
        ax.text(0, -0.30, "tamamlandi", fontsize=8, color="#7A8AA3",
                ha="center", va="center")
        # Proje adi ust
        theme = cfg.PROJECT_THEMES.get(proj, {})
        accent = "#" + theme.get("card_accent", "1B3A6B")
        ax.set_title(proj, fontsize=14, fontweight="bold", color=accent, pad=12)
        # Toplam
        ax.text(0, -1.30, f"{s['total']} görev", fontsize=10,
                color="#5A6A85", ha="center", va="center", style="italic")

    # ── Bar chart: Aktif görevler proje × durum ──
    ax_b = fig.add_subplot(gs[3, :])
    ax_b.set_facecolor("white")
    states = ["in_progress", "todo", "blocked"]
    state_labels = ["Devam Ediyor", "Yapılacak", "Beklemede"]
    state_colors = ["#2980B9", "#95A5A6", "#E67E22"]

    import numpy as np
    x = np.arange(len(proj_codes))
    width = 0.25
    for j, (st, lbl, c) in enumerate(zip(states, state_labels, state_colors)):
        vals = [stats["projects"][p][st] for p in proj_codes]
        offsets = (j - 1) * width
        bars = ax_b.bar(x + offsets, vals, width, label=lbl,
                        color=c, edgecolor="white", linewidth=1.5)
        for b, v in zip(bars, vals):
            if v > 0:
                ax_b.text(b.get_x() + b.get_width()/2, b.get_height() + 0.3,
                          str(v), ha="center", fontsize=9,
                          fontweight="bold", color=c)
    ax_b.set_xticks(x)
    ax_b.set_xticklabels(proj_codes, fontsize=11, fontweight="bold")
    ax_b.set_title("Aktif Görevler — Proje × Durum",
                   fontsize=12, fontweight="bold", color="#1B3A6B",
                   loc="left", pad=10)
    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)
    ax_b.spines["left"].set_color("#DDDDDD")
    ax_b.spines["bottom"].set_color("#DDDDDD")
    ax_b.tick_params(left=False)
    ax_b.legend(loc="upper right", frameon=False, fontsize=9, ncol=3)
    ax_b.set_axisbelow(True)
    ax_b.yaxis.grid(True, linestyle="--", alpha=0.4)

    # ── Urgent listesi ──
    ax_u = fig.add_subplot(gs[4, :])
    ax_u.set_facecolor("#FFFFFF")
    ax_u.set_xlim(0, 1); ax_u.set_ylim(0, 1)
    ax_u.axis("off")
    # Title
    ax_u.text(0.01, 0.96, "▶  ACİL GÖREVLER",
              fontsize=14, fontweight="bold", color="#C0392B")
    urgent = stats["urgent"][:8]
    if not urgent:
        ax_u.text(0.5, 0.5, "✓ Tüm görevler zamanında",
                  fontsize=14, color="#27AE60", ha="center")
    else:
        # Header satiri
        y = 0.86
        # Liste
        for i, item in enumerate(urgent):
            yy = 0.80 - i * 0.095
            # alt satir cizgisi
            ax_u.plot([0.01, 0.99], [yy + 0.05, yy + 0.05],
                      color="#EEEEEE", linewidth=1)
            # badge (proje + acil etiket)
            theme = cfg.PROJECT_THEMES.get(item["proj"], {})
            badge_bg = "#" + theme.get("badge_bg", "EEEEEE")
            badge_fg = "#" + theme.get("badge_color", "333333")
            ax_u.add_patch(Rectangle((0.01, yy), 0.07, 0.06,
                facecolor=badge_bg, edgecolor=badge_fg, linewidth=1))
            ax_u.text(0.045, yy + 0.03, item["proj"],
                fontsize=8, fontweight="bold", color=badge_fg,
                ha="center", va="center")
            # acil tag
            ax_u.add_patch(Rectangle((0.085, yy), 0.10, 0.06,
                facecolor=item["color"], edgecolor="none"))
            ax_u.text(0.135, yy + 0.03, item["due_label"],
                fontsize=8, fontweight="bold", color="white",
                ha="center", va="center")
            # key
            ax_u.text(0.20, yy + 0.03, item["key"],
                fontsize=10, fontweight="bold", color="#1B3A6B", va="center")
            # summary (truncated)
            summary = item["summary"]
            if len(summary) > 50:
                summary = summary[:50] + "…"
            ax_u.text(0.30, yy + 0.03, summary,
                fontsize=10, color="#2C3E50", va="center")
            # assignee
            ax_u.text(0.99, yy + 0.03, item["assignee"],
                fontsize=9, color="#5A6A85", va="center", ha="right",
                style="italic")

    # ── Footer ──
    ax_f = fig.add_subplot(gs[5, :])
    ax_f.axis("off")
    ax_f.text(0.5, 0.5,
        f"Toplam {sum(p['total'] for p in stats['projects'].values())} görev   |   "
        f"Detay için Excel raporuna bakınız   |   "
        f"{datetime.now().strftime('%d.%m.%Y %H:%M')}",
        fontsize=9, color="#7A8AA3", ha="center", va="center", style="italic")

    # Save to buffer
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=110, facecolor="#F7F9FC",
                bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()

# ---- Telegram sendPhoto ---------------------------------------------------
def send_photo(png_bytes, caption, chat_id=None):
    """multipart/form-data ile sendPhoto. urllib + boundary manuel."""
    chat = chat_id or cfg.TG_CHAT
    boundary = "----JiraVisualBoundary" + datetime.now().strftime("%H%M%S")
    body = []
    def part(name, value):
        body.append(("--" + boundary).encode())
        body.append(f'Content-Disposition: form-data; name="{name}"'.encode())
        body.append(b"")
        body.append(str(value).encode("utf-8"))
    # text fields
    part("chat_id", chat)
    part("caption", caption)
    part("parse_mode", "HTML")
    # file field
    body.append(("--" + boundary).encode())
    body.append(b'Content-Disposition: form-data; name="photo"; filename="dashboard.png"')
    body.append(b"Content-Type: image/png")
    body.append(b"")
    body.append(png_bytes)
    body.append(("--" + boundary + "--").encode())

    data = b"\r\n".join(body)
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{cfg.TG_TOKEN}/sendPhoto",
        data=data,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            r = json.loads(resp.read().decode())
            return r.get("ok", False), r
    except Exception as e:
        return False, str(e)

# ---- Main -----------------------------------------------------------------
def main():
    test_mode = "--test" in sys.argv
    log("=== Telegram Gorsel Dashboard basladi" + (" (TEST)" if test_mode else "") + " ===")

    log("1) Jira'dan veri cekiliyor...")
    stats = gather_stats()
    log(f"   Toplam {sum(p['total'] for p in stats['projects'].values())} gorev, "
        f"{len(stats['urgent'])} acil")

    log("2) Dashboard PNG uretiliyor...")
    png = make_dashboard(stats)
    log(f"   PNG boyutu: {len(png)/1024:.1f} KB")

    # Caption
    total = sum(p["total"] for p in stats["projects"].values())
    overdue = sum(p["overdue"] for p in stats["projects"].values())
    today = sum(p["today"] for p in stats["projects"].values())
    caption = (
        f"📊 <b>Günlük Dashboard</b> — {TODAY.day:02d}.{TODAY.month:02d}.{TODAY.year}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Toplam: <b>{total}</b> görev\n"
        f"🔴 Geciken: <b>{overdue}</b>\n"
        f"🟠 Bugün: <b>{today}</b>\n"
    )
    if test_mode:
        caption = "[TEST] " + caption

    log("3) Telegram'a gonderiliyor...")
    ok, resp = send_photo(png, caption)
    if ok:
        log(f"   GONDERILDI -> chat={cfg.TG_CHAT}")
    else:
        log(f"   HATA: {resp}")
        sys.exit(1)

    log("=== Bitti ===")

if __name__ == "__main__":
    main()
