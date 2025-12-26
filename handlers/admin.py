from vkbottle.bot import BotLabeler, Message
from database.models import User, TransactionLog, Promo, Cheque, ShopRequest, RequestStatus
from settings import ADMIN_IDS
from utils.helpers import get_id_from_mention
from tortoise.transactions import in_transaction
from datetime import datetime
import re

labeler = BotLabeler()

# --- 🔥 НОВАЯ ФУНКЦИЯ: АВТО-ОБНОВЛЕНИЕ КАРТОЧКИ ---
async def auto_update_card(api, user_db):
    if not user_db.card_photo_id: return
    try:
        new_desc = f"✦ ДОСЬЕ ИГРОКА ✦\n\n👤 Имя: {user_db.first_name}\n☢ Ранг: {user_db.get_rank()}\n💰 Баланс: {user_db.balance} чилликов\n\nОбновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        owner_id, photo_id = user_db.card_photo_id.split('_')
        await api.photos.edit(owner_id=int(owner_id), photo_id=int(photo_id), caption=new_desc)
    except: pass

# --- ПОМОЩНИК: ПОЛУЧЕНИЕ ИМЕНИ ---
async def get_name(message: Message, user_id: int) -> str:
    user = await User.get_or_none(vk_id=user_id)
    if user and user.first_name != "Неизвестный":
        return user.first_name
    try:
        users_info = await message.ctx_api.users.get(user_ids=[user_id])
        return users_info[0].first_name
    except:
        return "User"

# --- КОМАНДА: НАЧИСЛИТЬ ---
@labeler.message(regex=r"^(?i)Начислить\s+(.*?)\s+(\d+)$")
async def admin_give(message: Message, match):
    if message.from_id not in ADMIN_IDS: return

    target_raw, amount_str = match[0], match[1]
    amount = int(amount_str)
    target_id = get_id_from_mention(target_raw)

    if not target_id:
        return await message.answer("❌ Не понял, кому. Укажи @user.")

    name = await get_name(message, target_id)
    user = await User.get_or_none(vk_id=target_id)
    if not user:
        user = await User.create(vk_id=target_id, first_name=name, last_name="Player")

    user.balance += amount
    user.first_name = name
    await user.save()
    
    # 🔥 ОБНОВЛЯЕМ КАРТОЧКУ
    await auto_update_card(message.ctx_api, user) 
    
    await TransactionLog.create(user=user, amount=amount, description="Админ выдал")

    await message.answer(f"✅ Админ-чит сработал.\nВыдано {amount} Чилликов пользователю [id{target_id}|{name}].")

# --- КОМАНДА: СПИСАТЬ ---
@labeler.message(regex=r"^(?i)Списать\s+(.*?)\s+(\d+)$")
async def admin_remove(message: Message, match):
    if message.from_id not in ADMIN_IDS: return

    target_raw, amount_str = match[0], match[1]
    amount = int(amount_str)
    target_id = get_id_from_mention(target_raw)

    if not target_id: return await message.answer("❌ Кому?")
    
    name = await get_name(message, target_id)
    user = await User.get_or_none(vk_id=target_id)
    if not user: return await message.answer("❌ Такого нет в базе.")

    user.balance -= amount
    await user.save()

    # 🔥 ОБНОВЛЯЕМ КАРТОЧКУ
    await auto_update_card(message.ctx_api, user)

    await TransactionLog.create(user=user, amount=-amount, description="Админ забрал")

    await message.answer(f"✅ Налоговая тут.\nСписано {amount} Чилликов у [id{target_id}|{name}].")

# --- КОМАНДА: БАН ---
@labeler.message(regex=r"^(?i)Попущенный\s+(.*?)(?:\s+(.*))?$")
async def admin_ban(message: Message, match):
    if message.from_id not in ADMIN_IDS: return

    target_raw = match[0]
    reason = match[1] or "Без причины"
    target_id = get_id_from_mention(target_raw)

    if not target_id: return await message.answer("❌ Кого баним?")

    name = await get_name(message, target_id)
    user = await User.get_or_none(vk_id=target_id)
    if not user:
        user = await User.create(vk_id=target_id, first_name=name, last_name="Banned")
    
    user.is_banned = True
    await user.save()

    await message.answer(f"⛔ Пользователь [id{target_id}|{name}] теперь официально Попущенный.\nПричина: {reason}")

# --- КОМАНДА: РАЗБАН ---
@labeler.message(regex=r"^(?i)Разбан\s+(.*?)$")
async def admin_unban(message: Message, match):
    if message.from_id not in ADMIN_IDS: return

    target_id = get_id_from_mention(match[0])
    if not target_id: return await message.answer("❌ Кого?")
    
    name = await get_name(message, target_id)
    user = await User.get_or_none(vk_id=target_id)
    if not user: return await message.answer("❌ Не найден.")

    user.is_banned = False
    await user.save()
    await message.answer(f"✅ [id{target_id}|{name}] прощен.")

# --- КОМАНДА: РАССЫЛКА ---
@labeler.message(regex=r"^(?i)Рассылка\s+(.*)$")
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
            pass 
    
    await message.answer(f"✅ Рассылка завершена. Доставлено: {count}/{len(users)}")

# --- КОМАНДА: ПРОМОКОД ---
@labeler.message(regex=r"^(?i)Промокод\s+(\w+)\s+(\d+)\s+(\d+)$")
async def create_promo(message: Message, match):
    if message.from_id not in ADMIN_IDS: return

    code, amount, activations = match[0], int(match[1]), int(match[2])
    
    await Promo.create(code=code, amount=amount, max_activations=activations)
    await message.answer(f"🎫 Промокод {code} создан!\nСумма: {amount}\nАктиваций: {activations}")

# --- 🔥 КОМАНДА: ОТВЕТ НА ЗАЯВКУ (Стоимость) 🔥 ---
@labeler.message(regex=r"^(?i)Стоимость:\s+(\d+)$")
async def set_price(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    if not message.reply_message: return await message.answer("❌ Ответь на сообщение с заявкой!")

    price = int(match[0])
    reply_text = message.reply_message.text
    
    # 1. Ищем ID игрока в тексте заявки: [id12345|Name]
    user_match = re.search(r"\[id(\d+)\|", reply_text)
    # 2. Ищем номер заявки: ЗАЯВКА №1
    req_match = re.search(r"ЗАЯВКА №(\d+)", reply_text)
    
    if not user_match:
        return await message.answer("❌ Не могу найти ID игрока в сообщении. Формат нарушен?")
    
    target_id = int(user_match.group(1))
    
    # Обновляем заявку в БД (если нашли номер)
    if req_match:
        req_id = int(req_match.group(1))
        request = await ShopRequest.get_or_none(id=req_id)
        if request:
            request.price = price
            request.status = RequestStatus.PRICE_SET
            await request.save()

    # Отправляем уведомление игроку
    try:
        await message.ctx_api.messages.send(
            peer_id=target_id,
            message=(
                f"🏪 МАГАЗИН УВЕДОМЛЕНИЕ\n"
                f"✅ Администратор оценил твой заказ!\n\n"
                f"💰 Стоимость: {price} Чилликов\n"
                f"Чтобы оплатить, переведи эту сумму админу или договорись лично."
            ),
            random_id=0
        )
        await message.answer(f"✅ Цена {price} установлена. Уведомление отправлено [id{target_id}|игроку].")
    except Exception as e:
        await message.answer(f"⚠ Цену сохранил, но ЛС у игрока закрыто. Ошибка: {e}")
