import os
from aiohttp import web
from vkbottle import Bot
from tortoise import Tortoise

# ВАЖНО: Исправлен импорт (middleware без 's', как у тебя в папке)
from handlers import economy, shop, admin
from middleware.system import SystemMiddleware
from settings import VK_GROUP_TOKEN, DATABASE_URL

# Инициализация бота
bot = Bot(token=VK_GROUP_TOKEN)
bot.labeler.message_view.register_middleware(SystemMiddleware)
bot.labeler.load(economy.labeler)
bot.labeler.load(shop.labeler)
bot.labeler.load(admin.labeler)

# --- Функции запуска (База + Веб-сервер для Render) ---

async def init_db():
    print("💾 Connecting to DB...")
    await Tortoise.init(db_url=DATABASE_URL, modules={'models': ['database.models']})
    await Tortoise.generate_schemas()
    print("✅ DB Connected")

async def handle_ping(request):
    return web.Response(text="Bot is chilling.")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌍 Web server running on port {port}")

# Добавляем задачи в автозапуск: когда бот проснется, он запустит БД и сервер
bot.loop_wrapper.on_startup.append(init_db)
bot.loop_wrapper.on_startup.append(start_web_server)

if __name__ == "__main__":
    print("🚀 Bot starting...")
    # run_forever() сам создает нужный цикл и держит бота включенным
    bot.run_forever()
