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
TO          = _cfg.MAIL_TO
CC          = list(_cfg.MAIL_CC)

# E-posta kullanici adindan dogal hitap olustur
# "talhacemil@..." -> "Talha Cemil Bey"
NAME_OVERRIDES = {
    "talhacemil":   "Talha Cemil Bey",
    "myusufyanik":  "Muhammed Yusuf Bey",
    "ugurdemirhan": "Uğur Bey",
    "yusufliman":   "Yusuf Bey",
    "burcinaksu":   "Burçin Hanım",
}

PROJECT_NAMES = ["RPA", "GNDFAB", "GNDERP", "ODOO"]

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
    msg["Subject"] = "Dijital Donusum Proje Raporu | " + datetime.now().strftime("%d.%m.%Y")

    now = datetime.now()
    hitap = hitap_olustur(TO)
    kapsam = " & ".join(PROJECT_NAMES) + " Proje Panoları"
    body = (
        hitap + ",\n\n"
        "Gündoğdu Gıda Dijital Dönüşüm süreci kapsamında hazırlanan güncel proje "
        "ilerleme raporu ekte sunulmaktadır.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  RAPOR DETAYLARI\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  Rapor Tarihi  : " + now.strftime("%d.%m.%Y") + "\n"
        "  Rapor Saati   : " + now.strftime("%H:%M") + "\n"
        "  Kapsam        : " + kapsam + "\n"
        "  Dosya Adı     : " + os.path.basename(latest) + "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Raporun içeriği:\n"
        "  • Ana Sayfa    : Tüm projelere ait özet kartlar\n"
        "  • Yol Haritası : Tarihli görevlerin deadline takvimi\n"
        "  • Pano sayfaları : Her proje için detaylı görev listesi\n"
        "  • Erken / Geç tamamlanmış görev tespiti\n"
        "  • Süresi geçmiş ve yaklaşan görevlerin uyarıları\n\n"
        "Herhangi bir konuda bilgi almak için bu e-postaya yanıt verebilirsiniz.\n\n"
        "Saygılarımla,\n"
        "Gündoğdu Gıda — Dijital Dönüşüm Ekibi\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Bu rapor her sabah 08:00'de otomatik olarak oluşturulup gönderilmektedir.\n"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

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
            smtp.sendmail(SENDER, [TO] + CC, msg.as_string())
        log("E-posta gonderildi -> " + TO)
    except Exception as e:
        log("E-posta HATASI: " + str(e))
        sys.exit(1)

    log("=== Gorev tamamlandi ===")

if __name__ == "__main__":
    main()
