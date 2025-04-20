import os

BOT_TOKEN    = os.getenv("BOT_TOKEN")       # Ваш токен бота
# ADMIN_IDS берётся из ENV в формате "12345678,87654321"
ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "")
                .split(",") if x.strip()
] 
# Пример: "12345678,87654321"

# для Webhook
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")    
# Пример: "https://<your-app>.onrender.com"
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL  = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEBAPP_HOST  = "0.0.0.0"
WEBAPP_PORT  = int(os.getenv("PORT", "8000"))
