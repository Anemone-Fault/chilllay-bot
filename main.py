import os
from aiohttp import web
from vkbottle import Bot
from tortoise import Tortoise

# Импорты (middleware без s - как у тебя в папке)
from handlers import economy, shop, admin
from middleware.system import SystemMiddleware
from settings import VK_GROUP_TOKEN, DATABASE_URL

# 1. Инициализация бота
bot = Bot(token=VK_GROUP_TOKEN)
bot.labeler.message_view.register_middleware(SystemMiddleware)
bot.labeler.load(economy.labeler)
bot.labeler.load(shop.labeler)
bot.labeler.load(admin.labeler)

# --- 2. Настройка базы данных (через декоратор startup) ---
@bot.loop_wrapper.on_startup
async def init_db():
    print("💾 Connecting to DB...")
    # Подключаем Tortoise ORM
    await Tortoise.init(db_url=DATABASE_URL, modules={'models': ['database.models']})
    # Генерируем таблицы
    await Tortoise.generate_schemas()
    print("✅ DB Connected")

# --- 3. Настройка веб-сервера для Render (через декоратор startup) ---
async def handle_ping(request):
    return web.Response(text="Bot is chilling.")

@bot.loop_wrapper.on_startup
async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render передает порт через переменную окружения, или используем 8080
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    await site.start()
    print(f"🌍 Web server running on port {port}")

# --- 4. Запуск ---
if __name__ == "__main__":
    print("🚀 Bot starting...")
    # run_polling сам запустит функции выше (init_db и start_web_server)
    # и начнет принимать сообщения от ВК
    bot.run_polling()
