import os
from dotenv import load_dotenv

load_dotenv()

VK_GROUP_TOKEN = os.getenv("VK_GROUP_TOKEN")
# Если ID не указан, ставим 0, чтобы не крашилось сразу, но бот должен знать свой ID
VK_GROUP_ID = int(os.getenv("VK_GROUP_ID", 0))

# Безопасная обработка списка админов
admin_ids_str = os.getenv("ADMIN_IDS", "")
try:
    ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]
except:
    ADMIN_IDS = []
    print("⚠️ Ошибка парсинга ADMIN_IDS. Список админов пуст.")

# Фикс для Tortoise ORM (Supabase дает postgresql://, а нужен postgres://)
raw_db_url = os.getenv("DATABASE_URL", "")
DATABASE_URL = raw_db_url.replace("postgresql://", "postgres://")

RATE_LIMIT_SECONDS = float(os.getenv("RATE_LIMIT_SECONDS", 1.5))
STARTING_BALANCE = int(os.getenv("STARTING_BALANCE", 1000))