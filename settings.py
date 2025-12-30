import os
from dotenv import load_dotenv

load_dotenv()

VK_GROUP_TOKEN = os.getenv("VK_GROUP_TOKEN")
VK_GROUP_ID = int(os.getenv("VK_GROUP_ID", 0))
USER_TOKEN = os.getenv("USER_TOKEN")
ADMIN_USER_TOKEN = os.getenv("ADMIN_USER_TOKEN")

# ID чатов
RP_CHAT_ID = int(os.getenv("RP_CHAT_ID", 0))    
MAIN_CHAT_ID = int(os.getenv("MAIN_CHAT_ID", 0)) 

# Админы
admin_ids_str = os.getenv("ADMIN_IDS", "")
try:
    ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]
except:
    ADMIN_IDS = []

# Фикс базы для Supabase
raw_db_url = os.getenv("DATABASE_URL", "")
DATABASE_URL = raw_db_url.replace("postgresql://", "postgres://")

RATE_LIMIT_SECONDS = float(os.getenv("RATE_LIMIT_SECONDS", 1.5))
STARTING_BALANCE = int(os.getenv("STARTING_BALANCE", 1000))

# Картинки категорий
GIFT_IMAGES = {
    "Чилликовый": None, 
    "Предметный": None,
    "Талантливый": None,
    "Удачливый": None,
    "Судьбоносный": None
}
