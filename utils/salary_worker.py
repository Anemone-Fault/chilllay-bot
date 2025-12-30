from vkbottle import Bot
from database.models import User, SystemConfig
from utils.card_updater import auto_update_card
from settings import MAIN_CHAT_ID
from datetime import datetime
import asyncio

async def check_and_pay_salary(bot: Bot):
    now = datetime.now()
    current_month_key = f"{now.year}-{now.month}" 
    last_payout, _ = await SystemConfig.get_or_create(key="last_salary_month", defaults={"value": ""})

    if last_payout.value == current_month_key:
        return

    # ВЫДАЧА
    print("💰 Выдача зарплаты...")
    users = await User.filter(rp_pending_balance__gt=0).order_by("-rp_monthly_chars").all()
    
    if not users:
        last_payout.value = current_month_key
        await last_payout.save()
        return

    # ОТЧЕТ
    report = (
        f"╔═══════════════╗\n"
        f"  💸 ИТОГИ МЕСЯЦА\n"
        f"╚═══════════════╝\n\n"
        f"📅 Месяц завершен.\n"
        f"Зарплата переведена!\n\n"
        f"🏆 ТОП АКТИВНЫХ:\n"
        f"━━━━━━━━━━━━━━━\n"
    )

    top_3 = ["🥇", "🥈", "🥉"]
    for i, user in enumerate(users):
        amount = user.rp_pending_balance
        user.balance += amount
        user.rp_pending_balance = 0
        user.rp_monthly_chars = 0 # Сброс
        await user.save()
        
        # Обновляем карту
        await auto_update_card(bot.api, user)
        await asyncio.sleep(0.5)

        if i < 10:
            medal = top_3[i] if i < 3 else "🔸"
            report += f"{medal} {user.first_name} — {amount} 💰\n"

    if MAIN_CHAT_ID != 0:
        try: await bot.api.messages.send(peer_id=MAIN_CHAT_ID, message=report, random_id=0)
        except: pass

    last_payout.value = current_month_key
    await last_payout.save()
