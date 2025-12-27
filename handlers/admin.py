from vkbottle.bot import BotLabeler, Message
from vkbottle import VKAPIError
from database.models import User, TransactionLog, Promo, Cheque, ShopRequest, RequestStatus
from settings import ADMIN_IDS
from utils.helpers import get_id_from_mention
from datetime import datetime
import re

labeler = BotLabeler()

# --- 🔥 ФУНКЦИЯ: ОБНОВЛЕНИЕ КАРТОЧКИ (Через описание фото) ---
async def auto_update_card(api, user_db, debug_message: Message = None):
    if not user_db.card_photo_id: 
        if debug_message: await debug_message.answer("❌ В базе нет ID фото.")
        return

    # Текст, который будет в ОПИСАНИИ фото
    dossier_text = (
        f"✦ ДОСЬЕ ИГРОКА ✦\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 Игрок: {user_db.first_name}\n"
        f"☢ Ранг: {user_db.get_rank()}\n"
        f"💰 Баланс: {user_db.balance} чилликов\n"
        f"🕒 Обновлено: {datetime.now().strftime('%H:%M')}\n"
        f"━━━━━━━━━━━━━━━"
    )

    try:
        # Парсим ID: "-123_456" -> owner_id=-123, photo_id=456
        owner_id, photo_id = map(int, user_db.card_photo_id.split('_'))

        # Проверка: Если фото группы, owner_id должен быть отрицательным
        # Метод photos.edit идеально работает для фоток группы
        await api.photos.edit(
            owner_id=owner_id,
            photo_id=photo_id,
            caption=dossier_text
        )

        print(f"✅ Описание фото {photo_id} обновлено.", flush=True)
        if debug_message: await debug_message.answer(f"✅ Карточка обновлена (изменено описание).")

    except VKAPIError as e:
        # ИСПРАВЛЕНИЕ: Используем .error_msg вместо .description
        err_msg = getattr(e, "error_msg", str(e))
        err_text = f"🔥 Ошибка ВК (Код {e.code}): {err_msg}"
        print(err_text, flush=True)
        
        if debug_message: 
            await debug_message.answer(f"❌ {err_text}")
            
    except Exception as e:
        err_text = f"🔥 Системная ошибка: {e}"
        print(err_text, flush=True)
        if debug_message: await debug_message.answer(f"❌ {err_text}")


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

# --- КОМАНДА: ТЕСТ КАРТОЧКИ ---
@labeler.message(text="/test_card")
async def debug_card_cmd(message: Message):
    if message.from_id not in ADMIN_IDS: return
    user = await User.get_or_none(vk_id=message.from_id)
    if not user or not user.card_photo_id: return await message.answer("❌ Нет привязанной карты.")
    await message.answer(f"🔍 Диагностика для {user.card_photo_id}...")
    await auto_update_card(message.ctx_api, user, debug_message=message)

# --- КОМАНДА: НАЧИСЛИТЬ ---
@labeler.message(regex=r"^(?i)Начислить\s+(.*?)\s+(\d+)$")
async def admin_give(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    target_raw, amount_str = match[0], match[1]
    amount = int(amount_str)
    target_id = get_id_from_mention(target_raw)

    if not target_id: return await message.answer("❌ Кому?")
    name = await get_name(message, target_id)
    user = await User.get_or_none(vk_id=target_id)
    if not user: user = await User.create(vk_id=target_id, first_name=name, last_name="Player")

    user.balance += amount
    user.first_name = name
    await user.save()
    
    await auto_update_card(message.ctx_api, user) 
    await TransactionLog.create(user=user, amount=amount, description="Админ выдал")
    await message.answer(f"✅ Выдано {amount} [id{target_id}|{name}].")

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
    if not user: return await message.answer("❌ Нет в базе.")

    user.balance -= amount
    await user.save()
    await auto_update_card(message.ctx_api, user)
    await TransactionLog.create(user=user, amount=-amount, description="Админ забрал")
    await message.answer(f"✅ Списано {amount} у [id{target_id}|{name}].")

# --- КОМАНДА: СВЯЗАТЬ КАРТОЧКУ ---
@labeler.message(regex=r"^(?i)Связать\s+(.*)$")
async def link_card(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    full_text = match[0] 
    photo_match = re.search(r"photo(-?\d+_\d+)", full_text)
    if not photo_match: return await message.answer("❌ Не вижу ссылку на фото.")
    full_photo_id = photo_match.group(1)

    target_id = None
    for word in full_text.split():
        uid = get_id_from_mention(word)
        if uid:
            target_id = uid
            break
    
    if not target_id: return await message.answer("❌ Не указан пользователь.")

    user = await User.get_or_none(vk_id=target_id)
    if not user:
        name = await get_name(message, target_id)
        user = await User.create(vk_id=target_id, first_name=name, last_name="Player")
    
    user.card_photo_id = full_photo_id
    # card_comment_id больше не нужен, так как мы редактируем само фото
    user.card_comment_id = None 
    await user.save()
    
    await message.answer(f"🔗 Связано! Обновляю описание...")
    await auto_update_card(message.ctx_api, user, debug_message=message)

# --- ОСТАЛЬНОЕ ---
@labeler.message(regex=r"^(?i)Попущенный\s+(.*?)(?:\s+(.*))?$")
async def admin_ban(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    target_id = get_id_from_mention(match[0])
    if not target_id: return
    user = await User.get_or_none(vk_id=target_id)
    if not user: return 
    user.is_banned = True
    await user.save()
    await message.answer(f"⛔ Забанен.")

@labeler.message(regex=r"^(?i)Разбан\s+(.*?)$")
async def admin_unban(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    target_id = get_id_from_mention(match[0])
    if user := await User.get_or_none(vk_id=target_id):
        user.is_banned = False
        await user.save()
        await message.answer("✅ Разбанен.")

@labeler.message(regex=r"^(?i)Рассылка\s+(.*)$")
async def admin_broadcast(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    text = match[0]
    users = await User.all()
    await message.answer(f"📢 Рассылка на {len(users)}.")
    for user in users:
        try: await message.ctx_api.messages.send(peer_id=user.vk_id, message=f"📢 {text}", random_id=0)
        except: pass

@labeler.message(regex=r"^(?i)Промокод\s+(\w+)\s+(\d+)\s+(\d+)$")
async def create_promo(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    await Promo.create(code=match[0], amount=int(match[1]), max_activations=int(match[2]))
    await message.answer(f"🎫 Промокод {match[0]} создан.")

@labeler.message(regex=r"^(?i)Стоимость:\s+(\d+)$")
async def set_price(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    if not message.reply_message: return
    price = int(match[0])
    user_match = re.search(r"\[id(\d+)\|", message.reply_message.text)
    req_match = re.search(r"ЗАЯВКА №(\d+)", message.reply_message.text)
    if user_match:
        target_id = int(user_match.group(1))
        if req_match:
            req = await ShopRequest.get_or_none(id=int(req_match.group(1)))
            if req:
                req.price = price
                req.status = RequestStatus.PRICE_SET
                await req.save()
        try: await message.ctx_api.messages.send(peer_id=target_id, message=f"💰 Оценка: {price}", random_id=0)
        except: pass
        await message.answer("✅ Оценено.")
