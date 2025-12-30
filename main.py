import os
import asyncio
from aiohttp import web
from vkbottle import Bot, GroupEventType
from tortoise import Tortoise

# Импорты
from handlers import economy, shop, admin, events
from utils import salary_worker
from middleware.system import SystemMiddleware
from database.models import User, GiftBox, Rarity, GiftType, SystemConfig
from settings import VK_GROUP_TOKEN, DATABASE_URL
from utils.card_updater import auto_update_card
import random

# Инициализация
bot = Bot(token=VK_GROUP_TOKEN)
bot.labeler.load(economy.labeler)
bot.labeler.load(shop.labeler)
bot.labeler.load(admin.labeler)
bot.labeler.load(events.labeler) 

# Регистрируем SystemMiddleware для анти-спама и счетчика зарплат
bot.labeler.message_view.register_middleware(SystemMiddleware)

# --- Хендлер Лайков (Дроп) ---
@bot.on.raw_event(GroupEventType.LIKE_ADD, dataclass=None)
async def handle_like(event: dict):
    obj = event["object"]
    if obj["liker_id"] < 0 or obj["object_type"] != "post": return

    # Проверка ивента
    event_conf = await SystemConfig.get_or_none(key="event_new_year")
    if not event_conf or event_conf.value != "True": return

    if random.random() > 0.20: return # 20% шанс

    user = await User.get_or_none(vk_id=obj["liker_id"])
    if user:
        box, _ = await GiftBox.get_or_create(user=user, rarity=Rarity.COMMON, gift_type=GiftType.MONEY)
        box.quantity += 1
        await box.save()
        try: await bot.api.messages.send(peer_id=user.vk_id, message="❤️ За лайк выпал кейс! Пиши /инвентарь", random_id=0)
        except: pass
        # Обновляем карту (на всякий случай)
        await auto_update_card(bot.api, user)

# --- Настройки ---
async def init_db():
    print("💾 DB Connecting...")
    await Tortoise.init(db_url=DATABASE_URL, modules={'models': ['database.models']})
    await Tortoise.generate_schemas()
    print("✅ DB Ready")

async def scheduler_loop():
    while True:
        await asyncio.sleep(60) 
        try:
            await salary_worker.check_and_pay_salary(bot)
        except Exception as e:
            print(f"Scheduler error: {e}")
        await asyncio.sleep(3600) 

async def handle_ping(request):
    return web.Response(text="Bot is alive.")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌍 Web server running on port {port}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    loop.run_until_complete(init_db())
    loop.run_until_complete(start_web_server())
    loop.create_task(scheduler_loop())
    
    # Чтобы бот использовал тот же луп
    bot.loop_wrapper.loop = loop
    
    print("🚀 Bot Started")
    bot.run_forever()
