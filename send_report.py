#!/usr/bin/env python3
import os, glob, smtplib, subprocess, sys
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime

RAPOR_DIR   = "/opt/jira_rapor/raporlar"
LOG_FILE    = "/opt/jira_rapor/rapor.log"
import sys as _sys
_sys.path.insert(0, "/opt/jira_rapor")
import config as _cfg
SMTP_SERVER = _cfg.SMTP_SERVER
SMTP_PORT   = _cfg.SMTP_PORT
SENDER      = _cfg.SMTP_SENDER
SENDER_NAME = _cfg.SMTP_NAME
USERNAME    = _cfg.SMTP_USERNAME
PASSWORD    = _cfg.SMTP_PASSWORD
TO_LIST = [
    "turabsaydam@gundogdugida.com",
    "ugurdemirhan@gundogdugida.com",
    "yusufliman@gundogdugida.com",
    "burcinaksu@gundogdugida.com",
    "sefasevinc@gundogdugida.com",
    "sametsayin@gundogdugida.com",
    "ebrarbulbul@gundogdugida.com",
]
CC          = ["myusufyanik@gundogdugida.com"]
TO          = ", ".join(TO_LIST)

# E-posta kullanici adindan dogal hitap olustur
# "talhacemil@..." -> "Talha Cemil Bey"
NAME_OVERRIDES = {
    "talhacemil":   "Talha Cemil Bey",
    "myusufyanik":  "Muhammed Yusuf Bey",
    "ugurdemirhan": "Uğur Bey",
    "yusufliman":   "Yusuf Bey",
    "burcinaksu":   "Burçin Hanım",
}

PROJECT_NAMES = list(_cfg.PROJECTS)  # config.py'den otomatik (yeni proje eklenince burayi degistirmeye gerek yok)

def hitap_olustur(email_addr):
    user = email_addr.split("@")[0].lower()
    if user in NAME_OVERRIDES:
        return "Sayın " + NAME_OVERRIDES[user]
    return "Merhaba"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "[" + ts + "] " + str(msg)
    print(line)
    with open(LOG_FILE, "a") as lf:
        lf.write(line + "\n")

def main():
    log("=== Rapor gorevi basladi ===")

    result = subprocess.run(
        ["python3", "/opt/jira_rapor/jira_to_excel.py"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        log("HATA: " + result.stderr[:500])
        sys.exit(1)
    log(result.stdout.strip())

    files = sorted(glob.glob(RAPOR_DIR + "/Digital_Donusum_*.xlsx"))
    if not files:
        log("HATA: Rapor dosyasi bulunamadi")
        sys.exit(1)

    latest = files[-1]
    log("Son rapor: " + latest)

    for old in files[:-5]:
        os.remove(old)
        log("Silindi: " + old)

    msg = MIMEMultipart()
    msg["From"]    = SENDER_NAME + " <" + SENDER + ">"
    msg["To"]      = TO
    msg["Cc"]      = ", ".join(CC)
    msg["Subject"] = "Günlük İş Programı | " + datetime.now().strftime("%d.%m.%Y")

    now = datetime.now()
    kapsam = " & ".join(PROJECT_NAMES)

    # HTML mail govdesi
    html = f"""<!DOCTYPE html>
<html lang="tr">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f3f5f9;font-family:Segoe UI,Calibri,Arial,sans-serif;color:#2c3e50;">
  <table width="100%" cellspacing="0" cellpadding="0" style="background:#f3f5f9;padding:24px 0;">
    <tr><td align="center">
      <table width="640" cellspacing="0" cellpadding="0" style="background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

        <!-- HEADER -->
        <tr>
          <td style="background:#ffffff;padding:32px 36px 26px 36px;border-bottom:4px solid #2E75B6;">
            <div style="font-size:24px;color:#1B3A6B;font-weight:800;letter-spacing:0.3px;">Gündoğdu Dairy Industry</div>
            <div style="margin-top:6px;font-size:15px;color:#2E75B6;font-weight:500;">{now.strftime('%d %B %Y, %A')}</div>
            <h1 style="margin:18px 0 0 0;font-size:24px;color:#1B3A6B;font-weight:700;letter-spacing:-0.3px;">
              GÜNLÜK İŞ PROGRAMI
            </h1>
          </td>
        </tr>

        <!-- HITAP -->
        <tr>
          <td style="padding:28px 36px 8px 36px;">
            <h2 style="margin:0 0 12px 0;font-size:20px;color:#1B3A6B;font-weight:600;">Merhaba Arkadaşlar 👋</h2>
            <p style="margin:0;font-size:15px;line-height:1.65;color:#3c4a5e;">
              Günlük çalışma programınızı <b>ekteki Excel raporuna göre</b> planlamanızı rica ederim.
              Her birinize atanmış görevler, başlangıç ve bitiş tarihleri, ilerleme durumları
              raporda detaylı şekilde yer almaktadır.
            </p>
          </td>
        </tr>

        <!-- INFO KARTLARI -->
        <tr>
          <td style="padding:18px 36px 8px 36px;">
            <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:separate;border-spacing:8px;">
              <tr>
                <td width="33%" style="background:#EBF2FA;border-left:4px solid #2E75B6;border-radius:8px;padding:14px 16px;">
                  <div style="font-size:11px;color:#5a78a3;letter-spacing:1.5px;font-weight:600;">RAPOR TARİHİ</div>
                  <div style="font-size:18px;color:#1B3A6B;font-weight:700;margin-top:4px;">{now.strftime('%d.%m.%Y')}</div>
                </td>
                <td width="33%" style="background:#EBF5E8;border-left:4px solid #3A7D2C;border-radius:8px;padding:14px 16px;">
                  <div style="font-size:11px;color:#5a8a55;letter-spacing:1.5px;font-weight:600;">SAAT</div>
                  <div style="font-size:18px;color:#1C4220;font-weight:700;margin-top:4px;">{now.strftime('%H:%M')}</div>
                </td>
                <td width="33%" style="background:#F3EBF7;border-left:4px solid #8E44AD;border-radius:8px;padding:14px 16px;">
                  <div style="font-size:11px;color:#7e5a9a;letter-spacing:1.5px;font-weight:600;">PROJELER</div>
                  <div style="font-size:14px;color:#4A148C;font-weight:700;margin-top:4px;">{kapsam}</div>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- TALIMATLAR -->
        <tr>
          <td style="padding:22px 36px 6px 36px;">
            <h3 style="margin:0 0 14px 0;font-size:17px;color:#1B3A6B;font-weight:600;">
              📌 Lütfen Dikkat
            </h3>
            <table width="100%" cellspacing="0" cellpadding="0">
              <tr><td style="padding:10px 14px;background:#fafbfd;border-left:3px solid #2E75B6;border-radius:6px;font-size:14px;line-height:1.55;">
                <b style="color:#1B3A6B;">1.</b> Günlük iş programınızı Excel'deki <b>sıralamaya göre</b> planlayın.
              </td></tr>
              <tr><td height="6"></td></tr>
              <tr><td style="padding:10px 14px;background:#fafbfd;border-left:3px solid #2E75B6;border-radius:6px;font-size:14px;line-height:1.55;">
                <b style="color:#1B3A6B;">2.</b> <b>Yol Haritası</b> sekmesinde size atanmış görevlerin tarihlerini takip edin.
              </td></tr>
              <tr><td height="6"></td></tr>
              <tr><td style="padding:10px 14px;background:#fafbfd;border-left:3px solid #D35400;border-radius:6px;font-size:14px;line-height:1.55;">
                <b style="color:#D35400;">3.</b> Süresi yaklaşan görevlere <b>öncelik veriniz</b>.
              </td></tr>
              <tr><td height="6"></td></tr>
              <tr><td style="padding:10px 14px;background:#fafbfd;border-left:3px solid #C0392B;border-radius:6px;font-size:14px;line-height:1.55;">
                <b style="color:#C0392B;">4.</b> Süresi geçmiş veya başlangıç tarihi gelmiş henüz açık olan görevlerinizi <b>bugün içinde</b> güncelleyin / tamamlayın.
              </td></tr>
              <tr><td height="6"></td></tr>
              <tr><td style="padding:10px 14px;background:#fafbfd;border-left:3px solid #27AE60;border-radius:6px;font-size:14px;line-height:1.55;">
                <b style="color:#27AE60;">5.</b> Tamamladığınız görevleri Jira üzerinde <b>'Tamam'</b> durumuna çekiniz.
              </td></tr>
            </table>
          </td>
        </tr>

        <!-- DOSYA -->
        <tr>
          <td style="padding:22px 36px 8px 36px;">
            <table width="100%" cellspacing="0" cellpadding="0" style="background:#1B3A6B;border-radius:10px;">
              <tr>
                <td style="padding:18px 22px;">
                  <div style="font-size:11px;color:#a8c4e8;letter-spacing:1.5px;font-weight:600;">EKTE</div>
                  <div style="font-size:15px;color:#ffffff;font-weight:600;margin-top:4px;">📊 {os.path.basename(latest)}</div>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- IMZA -->
        <tr>
          <td style="padding:24px 36px 8px 36px;">
            <p style="margin:0;font-size:14px;line-height:1.6;color:#3c4a5e;">
              Herhangi bir konuda bana e-posta ile ulaşabilirsiniz.<br>
              <i>İyi çalışmalar dilerim,</i>
            </p>
            <div style="margin-top:14px;padding-top:14px;border-top:2px solid #eef2f7;">
              <div style="font-size:16px;color:#1B3A6B;font-weight:700;">Muhammed Yusuf YANIK</div>
              <div style="font-size:13px;color:#7a8aa3;margin-top:2px;">Gündoğdu Gıda — Dijital Dönüşüm Ekibi</div>
            </div>
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="padding:18px 36px 26px 36px;">
            <div style="background:#f3f5f9;border-radius:8px;padding:12px 16px;font-size:12px;color:#7a8aa3;text-align:center;">
              ⏰ Bu mail her sabah <b>08:00</b>'de otomatik olarak gönderilmektedir.
            </div>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    # Plain-text fallback (HTML desteklemeyen mail clientlar icin)
    text_fallback = (
        "Merhaba Arkadaslar,\n\n"
        "Gunluk calisma programinizi ekteki Excel raporuna gore planlamanizi rica ederim.\n\n"
        f"Rapor: {os.path.basename(latest)}\n"
        f"Tarih: {now.strftime('%d.%m.%Y %H:%M')}\n"
        f"Projeler: {kapsam}\n\n"
        "Iyi calismalar,\nMuhammed Yusuf YANIK"
    )

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text_fallback, "plain", "utf-8"))
    alt.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(alt)

    with open(latest, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment; filename=" + os.path.basename(latest))
    msg.attach(part)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(USERNAME, PASSWORD)
            smtp.sendmail(SENDER, TO_LIST + CC, msg.as_string())
        log("E-posta gonderildi -> " + ", ".join(TO_LIST) + " (CC: " + ", ".join(CC) + ")")
    except Exception as e:
        log("E-posta HATASI: " + str(e))
        sys.exit(1)

    log("=== Gorev tamamlandi ===")

if __name__ == "__main__":
    main()
