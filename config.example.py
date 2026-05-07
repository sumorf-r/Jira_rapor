"""Merkezi konfigurasyon SABLONU.

Kullanim:
  cp config.example.py config.py
  chmod 600 config.py
  # Asagidaki degerleri kendi sirlarinla degistir
"""

# ---- Jira API ------------------------------------------------------------
JIRA_TOKEN = "ATATT...your_jira_api_token_here..."
JIRA_EMAIL = "you@example.com"
JIRA_BASE  = "https://your-company.atlassian.net"

# Jira Start Date custom field ID (Jira admin tarafindan set ediliyor).
# Eger Jira'da custom field rebuild olursa bu ID degisir.
JIRA_START_DATE_FIELD = "customfield_10015"

# ---- SMTP (Mail) ---------------------------------------------------------
SMTP_SERVER   = "smtp.example.com"
SMTP_PORT     = 587
SMTP_SENDER   = "noreply@example.com"
SMTP_NAME     = "Sender Name"
SMTP_USERNAME = "noreply@example.com"
SMTP_PASSWORD = "your_smtp_password"

# ---- Telegram ------------------------------------------------------------
TG_TOKEN = "1234567890:AABBccdd...your_bot_token..."
TG_CHAT  = "-100xxxxxxxxxx"  # Grup chat_id (negatif sayi)

# ---- Jira Webhook (real-time bildirimler) --------------------------------
# Opsiyonel: bot taramalarina karsi guvenlik. Set edilirse Jira webhook
# URL'inde ?token=<JIRA_WEBHOOK_SECRET> bekler.
# Bos brikabilir test icin, prod'da mutlaka set et.
JIRA_WEBHOOK_SECRET = ""  # ornek: "uzun-rastgele-string-32-karakter"

# ---- Mail alicilar -------------------------------------------------------
MAIL_TO = "primary@example.com"
MAIL_CC = [
    "cc1@example.com",
    "cc2@example.com",
]

# ---- Projeler ------------------------------------------------------------
PROJECTS = ["RPA", "GNDFAB"]  # Jira proje kodlari

# Her projenin tum renk/etiket bilgisi TEK YERDE.
# Yeni proje eklerken sadece PROJECTS listesine + buraya ekle.
PROJECT_THEMES = {
    "RPA": {
        "label":            "RPA  —  Robotic Process Automation",
        "sheet_color":      "1F4E79",
        "card_accent":      "1B3A6B",
        "card_btn":         "2E75B6",
        "card_stat_bg":     "EBF2FA",
        "card_stat_border": "C5D8F0",
        "badge_color":      "1B3A6B",
        "badge_bg":         "D6E4F0",
    },
    "GNDFAB": {
        "label":            "GNDFAB  —  Fabrika Yonetimi",
        "sheet_color":      "375623",
        "card_accent":      "1C4220",
        "card_btn":         "3A7D2C",
        "card_stat_bg":     "EBF5E8",
        "card_stat_border": "BBDDB0",
        "badge_color":      "1C4220",
        "badge_bg":         "D9EAD3",
    },
}

# ---- Rapor parametreleri -------------------------------------------------
# Pano "Ilerleme" cubugu icin referans pencere (gun).
# Bitis tarihinden bu kadar gun kala bar dolu sayilmaya baslar.
PROGRESS_WINDOW_PANO    = 30
# Yol Haritasi sheet'i (genelde daha genis).
PROGRESS_WINDOW_ROADMAP = 60

# ---- Dizinler/yollar -----------------------------------------------------
BASE_DIR    = "/opt/jira_rapor"
RAPOR_DIR   = "/opt/jira_rapor/raporlar"
YEDEK_DIR   = "/opt/jira_rapor/yedek"
