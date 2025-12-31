import os
import asyncio
from aiohttp import web
from vkbottle import Bot, GroupEventType
from tortoise import Tortoise

# Импорты хендлеров
from handlers import economy, shop, admin, events
from utils import salary_worker
from middleware.system import SystemMiddleware
from database.models import User, GiftBox, Rarity, GiftType, SystemConfig
from settings import VK_GROUP_TOKEN, DATABASE_URL, VK_GROUP_ID
from utils.card_updater import auto_update_card
import random


# ====================
# ИНИЦИАЛИЗАЦИЯ БОТА
# ====================

bot = Bot(token=VK_GROUP_TOKEN)

# Загружаем лейблеры
bot.labeler.load(economy.labeler)
bot.labeler.load(shop.labeler)
bot.labeler.load(admin.labeler)
bot.labeler.load(events.labeler)

# Регистрируем middleware
bot.labeler.message_view.register_middleware(SystemMiddleware)


# ====================
# ХЕНДЛЕР ЛАЙКОВ (ДРОП КЕЙСОВ)
# ====================

@bot.on.raw_event(GroupEventType.LIKE_ADD, dataclass=None)
async def handle_like(event: dict):
    """
    Обработчик лайков на постах.
    Выдает кейс с 20% шансом, если активен ивент.
    """
    obj = event["object"]
    
    # Игнорируем лайки от сообществ и лайки не на постах
    if obj["liker_id"] < 0 or obj["object_type"] != "post":
        return

    # Проверяем, активен ли ивент
    event_conf = await SystemConfig.get_or_none(key="event_new_year")
    if not event_conf or event_conf.value != "True":
        return

    # 20% шанс выпадения кейса
    if random.random() > 0.20:
        return

    # Получаем пользователя
    user = await User.get_or_none(vk_id=obj["liker_id"])
    if not user:
        return
    
    # Выдаем кейс
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
                "╔═════════════════════╗\n"
                "║  🎁 КЕЙС ВЫПАЛ!      ║\n"
                "╚═════════════════════╝\n\n"
                "❤️ За лайк поста!\n\n"
                "📦 Получен:\n"
                "   Обычный кейс\n\n"
                "{'═' * 25}\n\n"
                "Открой командой:\n"
                "🎒 Инвентарь"
            ),
            random_id=0
        )
    except:
        pass
    
    # Обновляем карточку
    await auto_update_card(bot.api, user)
    
    print(f"🎁 Кейс выдан {user.first_name} (ID: {user.vk_id}) за лайк!")


# ====================
# БАЗА ДАННЫХ
# ====================

async def init_db():
    """
    Инициализация подключения к базе данных.
    """
    print("\n╔═════════════════════╗")
    print("║  💾 БАЗА ДАННЫХ      ║")
    print("╚═════════════════════╝\n")
    print("⏳ Подключение к базе...")
    
    try:
        await Tortoise.init(
            db_url=DATABASE_URL,
            modules={'models': ['database.models']}
        )
        await Tortoise.generate_schemas()
        print("✅ База данных готова!\n")
    except Exception as e:
        print(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ К БД:\n{e}\n")
        raise


# ====================
# ПЛАНИРОВЩИК ЗАДАЧ
# ====================

async def scheduler_loop():
    """
    Бесконечный цикл для периодических задач.
    Проверяет зарплаты каждый час.
    """
    print("╔═════════════════════╗")
    print("║  ⏰ ПЛАНИРОВЩИК       ║")
    print("╚═════════════════════╝\n")
    print("✅ Планировщик запущен!")
    print("⏱ Проверка зарплат: каждый час\n")
    
    while True:
        await asyncio.sleep(60)  # Подождать минуту перед первой проверкой
        
        try:
            await salary_worker.check_and_pay_salary(bot)
        except Exception as e:
            print(f"⚠️ Ошибка в планировщике: {e}")
        
        await asyncio.sleep(3600)  # 1 час


# ====================
# ВЕБ-СЕРВЕР (KEEP-ALIVE)
# ====================

async def handle_ping(request):
    """
    Простой пинг-эндпоинт для проверки работы бота.
    """
    return web.Response(text="🤖 ChillLay Bot is alive and kicking! 💪")


async def handle_stats(request):
    """
    Эндпоинт с базовой статистикой.
    """
    try:
        users_count = await User.all().count()
        active_users = await User.filter(is_banned=False).count()
        total_balance = sum([u.balance for u in await User.all()])
        
        stats_text = (
            "╔═════════════════════╗\n"
            "║  📊 СТАТИСТИКА       ║\n"
            "╚═════════════════════╝\n\n"
            f"👥 Всего игроков: {users_count}\n"
            f"✅ Активных: {active_users}\n"
            f"💰 Общий баланс: {total_balance:,}₽\n"
        )
        
        return web.Response(text=stats_text)
    except:
        return web.Response(text="❌ Ошибка получения статистики")


async def start_web_server():
    """
    Запуск веб-сервера для keep-alive.
    """
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/stats", handle_stats)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    
    print("╔═════════════════════╗")
    print("║  🌍 ВЕБ-СЕРВЕР       ║")
    print("╚═════════════════════╝\n")
    print(f"✅ Сервер запущен!")
    print(f"🌐 Порт: {port}")
    print(f"📍 Эндпоинты:")
    print(f"   • GET / - проверка работы")
    print(f"   • GET /stats - статистика\n")


# ====================
# КРАСИВЫЙ СТАРТ
# ====================

def print_startup_banner():
    """
    Выводит красивый баннер при запуске.
    """
    banner = """
    ╔═══════════════════════════════════╗
    ║                                   ║
    ║     🎮 CHILLLAY RP BOT 🎮        ║
    ║                                   ║
    ║     Токсичный бот для ролевых    ║
    ║     Версия: 2.0 (Remastered)     ║
    ║                                   ║
    ╚═══════════════════════════════════╝
    """
    print(banner)
    print(f"🆔 ID группы: {VK_GROUP_ID if VK_GROUP_ID > 0 else 'Не указан'}")
    print(f"⚙️ Загружено хендлеров: 4")
    print(f"🔧 Middleware: SystemMiddleware\n")


# ====================
# ГЛАВНАЯ ФУНКЦИЯ
# ====================

if __name__ == "__main__":
    print_startup_banner()
    
    # Создаем event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Инициализация базы данных
        loop.run_until_complete(init_db())
        
        # Запуск веб-сервера
        loop.run_until_complete(start_web_server())
        
        # Запуск планировщика
        loop.create_task(scheduler_loop())
        
        # Связываем бота с текущим loop
        bot.loop_wrapper.loop = loop
        
        print("╔═════════════════════╗")
        print("║  🚀 БОТ ЗАПУЩЕН!     ║")
        print("╚═════════════════════╝\n")
        print("✅ Все системы работают!")
        print("⚡ Бот готов к работе!\n")
        print("{'═' * 40}\n")
        print("💬 Ожидание сообщений...\n")
        
        # Запуск бота
        bot.run_forever()
        
    except KeyboardInterrupt:
        print("\n\n╔═════════════════════╗")
        print("║  ⚠️ ОСТАНОВКА БОТА   ║")
        print("╚═════════════════════╝\n")
        print("👋 Бот остановлен пользователем!")
        
    except Exception as e:
        print("\n\n╔═════════════════════╗")
        print("║  ❌ КРИТИЧЕСКАЯ ОШИБКА ║")
        print("╚═════════════════════╝\n")
        print(f"Ошибка: {e}\n")
        raise
    
    finally:
        print("\n{'═' * 40}\n")
        print("🔄 Закрытие соединений...")
        loop.close()
        print("✅ Соединения закрыты!")
        print("\n👋 До встречи, нищеброды!\n")
