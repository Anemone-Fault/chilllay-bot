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
    """
    Обработчик лайков на записях сообщества.
    
    При активном ивенте с шансом 20% даёт игроку
    обычный денежный кейс за каждый лайк.
    
    Проверяет:
    - Лайк от реального пользователя (не от сообщества)
    - Лайк на пост (а не комментарий/фото)
    - Активность новогоднего ивента
    - Случайный шанс 20%
    """
    obj = event["object"]
    
    # Игнорируем лайки от сообществ и не на посты
    if obj["liker_id"] < 0 or obj["object_type"] != "post": 
        return

    # Проверка активности ивента
    event_conf = await SystemConfig.get_or_none(key="event_new_year")
    if not event_conf or event_conf.value != "True": 
        return

    # Шанс дропа 20%
    if random.random() > 0.20: 
        return

    user = await User.get_or_none(vk_id=obj["liker_id"])
    if user:
        # Создаём или добавляем обычный денежный кейс
        box, _ = await GiftBox.get_or_create(
            user=user, 
            rarity=Rarity.COMMON, 
            gift_type=GiftType.MONEY
        )
        box.quantity += 1
        await box.save()
        
        # Уведомляем игрока
        try: 
            await bot.api.messages.send(
                peer_id=user.vk_id, 
                message=(
                    "╔═══════════════════════╗\n"
                    "    🎁 КЕЙС ВЫПАЛ!\n"
                    "╚═══════════════════════╝\n\n"
                    "❤️ За лайк ты получил кейс!\n\n"
                    "┏━━━━ НАГРАДА ━━━━┓\n"
                    "│\n"
                    "│ 🎁 Тип: Денежный\n"
                    "│ ⚪ Ранг: Обычный\n"
                    "│ 📦 Количество: x1\n"
                    "│\n"
                    "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                    "💡 Открой его командой:\n"
                    "   Инвентарь\n\n"
                    "🎉 Ставь больше лайков для\n"
                    "   новых кейсов!"
                ), 
                random_id=0
            )
        except: 
            # Игнорируем ошибки (закрытые ЛС и т.д.)
            pass
        
        # Обновляем карточку игрока
        await auto_update_card(bot.api, user)

# --- Настройки ---
async def init_db():
    """Инициализация базы данных Tortoise ORM"""
    print("💾 Подключение к базе данных...")
    await Tortoise.init(
        db_url=DATABASE_URL, 
        modules={'models': ['database.models']}
    )
    await Tortoise.generate_schemas()
    print("✅ База данных готова к работе")

async def scheduler_loop():
    """
    Планировщик задач.
    
    Проверяет каждый час:
    - Необходимость выплаты месячной зарплаты
    - Другие периодические задачи
    """
    while True:
        await asyncio.sleep(60)  # Начальная задержка
        try:
            await salary_worker.check_and_pay_salary(bot)
        except Exception as e:
            print(f"⚠️ Ошибка планировщика: {e}")
        await asyncio.sleep(3600)  # Проверка раз в час

async def handle_ping(request):
    """Проверка работоспособности бота (для хостинга)"""
    return web.Response(text="Bot is alive.")

async def start_web_server():
    """
    Запуск веб-сервера для проверки статуса.
    
    Необходим для облачных хостингов (Heroku, Railway и т.д.),
    которые требуют HTTP-ответов для определения работоспособности.
    """
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌍 Веб-сервер запущен на порту {port}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    loop.run_until_complete(init_db())
    loop.run_until_complete(start_web_server())
    loop.create_task(scheduler_loop())
    
    # Чтобы бот использовал тот же луп
    bot.loop_wrapper.loop = loop
    
    print("🚀 Бот запущен и готов к работе!")
    bot.run_forever()
