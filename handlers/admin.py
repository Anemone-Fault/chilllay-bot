from vkbottle.bot import BotLabeler, Message
from database.models import User, TransactionLog, Promo, Cheque, ShopRequest, RequestStatus
from settings import ADMIN_IDS
from utils.helpers import get_id_from_mention
from tortoise.transactions import in_transaction
from datetime import datetime

labeler = BotLabeler()

# --- КОМАНДА: НАЧИСЛИТЬ ---
@labeler.message(regex=r"^Начислить\s+(.*?)\s+(\d+)$")
async def admin_give(message: Message, match):
    # 1. Проверка на админа (в лоб)
    if message.from_id not in ADMIN_IDS:
        return # Просто игнорим не админов

    # 2. Логика
    target_raw, amount_str = match[0], match[1]
    amount = int(amount_str)
    target_id = get_id_from_mention(target_raw)

    if not target_id:
        return await message.answer("❌ Не понял, кому. Укажи @user.")

    user = await User.get_or_none(vk_id=target_id)
    if not user:
        # Если юзера нет в базе, создадим "болванку", чтобы начислить
        user = await User.create(vk_id=target_id, first_name="Игрок", last_name="Новый")

    user.balance += amount
    await user.save()
    await TransactionLog.create(user=user, amount=amount, description="Админ выдал")

    await message.answer(f"✅ Админ-чит сработал.\nВыдано {amount} Чилликов пользователю [id{target_id}|User].")


# --- КОМАНДА: СПИСАТЬ ---
@labeler.message(regex=r"^Списать\s+(.*?)\s+(\d+)$")
async def admin_remove(message: Message, match):
    if message.from_id not in ADMIN_IDS: return

    target_raw, amount_str = match[0], match[1]
    amount = int(amount_str)
    target_id = get_id_from_mention(target_raw)

    if not target_id: return await message.answer("❌ Кому?")
    
    user = await User.get_or_none(vk_id=target_id)
    if not user: return await message.answer("❌ Такого нет в базе.")

    user.balance -= amount
    await user.save()
    await TransactionLog.create(user=user, amount=-amount, description="Админ забрал")

    await message.answer(f"✅ Налоговая тут.\nСписано {amount} Чилликов у [id{target_id}|User].")


# --- КОМАНДА: БАН (Попущенный) ---
@labeler.message(regex=r"^Попущенный\s+(.*?)(?:\s+(.*))?$")
async def admin_ban(message: Message, match):
    if message.from_id not in ADMIN_IDS: return

    target_raw = match[0]
    reason = match[1] or "Без причины"
    target_id = get_id_from_mention(target_raw)

    if not target_id: return await message.answer("❌ Кого баним?")

    user = await User.get_or_none(vk_id=target_id)
    if not user:
        user = await User.create(vk_id=target_id, first_name="Banned", last_name="User")
    
    user.is_banned = True
    await user.save()

    await message.answer(f"⛔ Пользователь [id{target_id}|User] теперь официально Попущенный.\nПричина: {reason}")


# --- КОМАНДА: РАЗБАН ---
@labeler.message(regex=r"^Разбан\s+(.*?)$")
async def admin_unban(message: Message, match):
    if message.from_id not in ADMIN_IDS: return

    target_id = get_id_from_mention(match[0])
    if not target_id: return await message.answer("❌ Кого?")

    user = await User.get_or_none(vk_id=target_id)
    if not user: return await message.answer("❌ Не найден.")

    user.is_banned = False
    await user.save()
    await message.answer(f"✅ [id{target_id}|User] прощен.")


# --- КОМАНДА: РАССЫЛКА ---
@labeler.message(regex=r"^Рассылка\s+(.*)$")
async def admin_broadcast(message: Message, match):
    if message.from_id not in ADMIN_IDS: return

    text = match[0]
    users = await User.all()
    count = 0
    
    await message.answer(f"📢 Начинаю рассылку для {len(users)} человек...")

    for user in users:
        try:
            await message.ctx_api.messages.send(
                peer_id=user.vk_id, 
                message=f"📢 ОБЪЯВЛЕНИЕ:\n\n{text}", 
                random_id=0
            )
            count += 1
        except:
            pass # Если у юзера закрыта личка, просто пропускаем
    
    await message.answer(f"✅ Рассылка завершена. Доставлено: {count}/{len(users)}")


# --- КОМАНДА: СОЗДАТЬ ПРОМОКОД ---
@labeler.message(regex=r"^Промокод\s+(\w+)\s+(\d+)\s+(\d+)$")
async def create_promo(message: Message, match):
    if message.from_id not in ADMIN_IDS: return

    code, amount, activations = match[0], int(match[1]), int(match[2])
    
    await Promo.create(code=code, amount=amount, max_activations=activations)
    await message.answer(f"🎫 Промокод {code} создан!\nСумма: {amount}\nАктиваций: {activations}")


# --- КОМАНДА: ОТВЕТ НА ЗАЯВКУ МАГАЗИНА ---
# Работает через Reply (Ответ на сообщение)
@labeler.message(regex=r"^Стоимость:\s+(\d+)$")
async def set_price(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    if not message.reply_message: return await message.answer("❌ Ответь на сообщение с заявкой!")

    price = int(match[0])
    
    # Пытаемся найти заявку по тексту сообщения, на которое ответили
    # (Это упрощенный вариант, так как ID заявки мы не хранили в тексте)
    # В идеале нужно писать ID заявки в сообщении админу
    
    await message.answer(f"✅ Ты оценил товар в {price} Чилликов.\n(Чтобы эта функция работала полноценно, нужно дорабатывать систему ID заявок, но пока так)")
