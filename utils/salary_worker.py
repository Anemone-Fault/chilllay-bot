from vkbottle import Bot
from database.models import User, SystemConfig
from utils.card_updater import auto_update_card
from settings import MAIN_CHAT_ID
from datetime import datetime
import asyncio


async def check_and_pay_salary(bot: Bot):
    """
    Проверяет и выплачивает зарплату в начале нового месяца.
    """
    now = datetime.now()
    current_month_key = f"{now.year}-{now.month}"
    
    # Получаем метку последней выплаты
    last_payout, _ = await SystemConfig.get_or_create(
        key="last_salary_month",
        defaults={"value": ""}
    )

    # Если в этом месяце уже платили, выходим
    if last_payout.value == current_month_key:
        return

    # ВЫДАЧА ЗАРПЛАТЫ
    print("╔═════════════════════╗")
    print("║  💰 ВЫДАЧА ЗАРПЛАТ   ║")
    print("╚═════════════════════╝")
    print(f"\n📅 Дата: {now.strftime('%d.%m.%Y %H:%M')}")
    print(f"🗓 Месяц: {current_month_key}\n")
    
    # Получаем игроков с зарплатой
    users = await User.filter(rp_pending_balance__gt=0).order_by("-rp_monthly_chars").all()
    
    if not users:
        print("⚠️ Нет игроков с зарплатой!")
        last_payout.value = current_month_key
        await last_payout.save()
        return

    print(f"👥 Найдено игроков: {len(users)}\n")
    print("{'═' * 40}\n")

    # Формируем отчет
    total_paid = 0
    top_3_medals = ["🥇", "🥈", "🥉"]
    
    report = (
        "╔═════════════════════╗\n"
        "║  💸 ИТОГИ МЕСЯЦА     ║\n"
        "╚═════════════════════╝\n\n"
        "📅 Месяц завершен!\n"
        "💰 Зарплата переведена!\n\n"
        "{'═' * 25}\n\n"
        "┌─ 🏆 ТОП АКТИВНЫХ\n"
        "│\n"
    )

    # Выплачиваем и формируем топ
    for i, user in enumerate(users):
        amount = user.rp_pending_balance
        chars_count = user.rp_monthly_chars
        
        # Переводим зарплату
        user.balance += amount
        user.rp_pending_balance = 0
        user.rp_monthly_chars = 0
        await user.save()
        
        total_paid += amount
        
        # Обновляем карту
        await auto_update_card(bot.api, user)
        await asyncio.sleep(0.5)  # Защита от флуда

        # Добавляем в отчет топ-10
        if i < 10:
            medal = top_3_medals[i] if i < 3 else f"├─ {i+1}."
            report += f"{medal} {user.first_name}\n"
            report += f"│  ├─ Получено: {amount:,}₽\n"
            report += f"│  └─ Символов: {chars_count:,}\n"
            
            if i == 2:  # После топ-3
                report += "│\n"
                report += f"├─ {'─' * 21}\n"
                report += "│\n"
        
        print(f"✅ {i+1}. {user.first_name} - {amount:,}₽ (символов: {chars_count:,})")

    report += "│\n"
    report += f"└─ {'─' * 21}\n\n"
    report += f"{'═' * 25}\n\n"
    report += f"💵 Всего выплачено:\n"
    report += f"   {total_paid:,}₽\n\n"
    report += f"👥 Получило зарплату:\n"
    report += f"   {len(users)} игроков\n\n"
    report += f"{'═' * 25}\n\n"
    report += "Красавчики! Проебете? 💸\n\n"
    report += "P.S. Начинаем новый месяц!\n"
    report += "     Фармите РП-посты! 📝"

    # Отправляем отчет в чат
    if MAIN_CHAT_ID != 0:
        try:
            await bot.api.messages.send(
                peer_id=MAIN_CHAT_ID,
                message=report,
                random_id=0
            )
            print(f"\n📢 Отчет отправлен в чат {MAIN_CHAT_ID}")
        except Exception as e:
            print(f"\n⚠️ Не удалось отправить отчет в чат: {e}")

    # Обновляем метку выплаты
    last_payout.value = current_month_key
    await last_payout.save()
    
    print("\n{'═' * 40}")
    print("✅ Зарплата успешно выплачена!")
    print("{'═' * 40}\n")
