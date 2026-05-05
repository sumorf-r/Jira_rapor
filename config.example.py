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

# ---- Mail alicilar -------------------------------------------------------
MAIL_TO = "primary@example.com"
MAIL_CC = [
    "cc1@example.com",
    "cc2@example.com",
]

# ---- Projeler ------------------------------------------------------------
PROJECTS = ["RPA", "GNDFAB"]  # Jira proje kodlari

# ---- Dizinler/yollar -----------------------------------------------------
BASE_DIR    = "/opt/jira_rapor"
RAPOR_DIR   = "/opt/jira_rapor/raporlar"
YEDEK_DIR   = "/opt/jira_rapor/yedek"
