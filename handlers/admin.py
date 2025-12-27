from vkbottle.bot import BotLabeler, Message
from database.models import User, TransactionLog, Promo, Cheque, ShopRequest, RequestStatus
from settings import ADMIN_IDS
from utils.helpers import get_id_from_mention
from tortoise.transactions import in_transaction
from datetime import datetime
import re

labeler = BotLabeler()

# --- 🔥 ФУНКЦИЯ: УМНЫЙ КОММЕНТАРИЙ (Edit or Create) ---
async def auto_update_card(api, user_db):
    if not user_db.card_photo_id: return

    # Текст досье в твоем формате
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
        # Разбираем ID фото: "-224755876_457239447" -> owner_id, photo_id
        owner_id, photo_id = map(int, user_db.card_photo_id.split('_'))

        # ВАРИАНТ 1: Если мы уже знаем ID комментария — пробуем редактировать
        if user_db.card_comment_id:
            try:
                await api.photos.edit_comment(
                    owner_id=owner_id,
                    comment_id=user_db.card_comment_id,
                    message=dossier_text
                )
                print(f"✅ [DEBUG] Комментарий {user_db.card_comment_id} обновлен.")
                return # Всё получилось, выходим
            except Exception as e:
                print(f"⚠ [DEBUG] Не вышло отредактировать (возможно, удален). Пишу новый. Ошибка: {e}")
                # Если ошибка (коммент удален руками), код пойдет дальше и создаст новый

        # ВАРИАНТ 2: Комментария нет или старый удален — создаем новый
        new_comment_id = await api.photos.create_comment(
            owner_id=owner_id,
            photo_id=photo_id,
            message=dossier_text
        )
        
        # Сохраняем ID нового комментария в базу
        user_db.card_comment_id = new_comment_id
        await user_db.save()
        print(f"🆕 [DEBUG] Создан новый комментарий ID {new_comment_id}")

    except Exception as e:
        print(f"🔥 [CRITICAL] Ошибка работы с комментарием: {e}")


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
    
    # 🔥 ОБНОВЛЯЕМ КОММЕНТ
    await auto_update_card(message.ctx_api, user) 
    
    await TransactionLog.create(user=user, amount=amount, description="Админ выдал")

    await message.answer(f"✅ Выдано {amount} пользователю [id{target_id}|{name}].")

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

    # 🔥 ОБНОВЛЯЕМ КОММЕНТ
    await auto_update_card(message.ctx_api, user)

    await TransactionLog.create(user=user, amount=-amount, description="Админ забрал")

    await message.answer(f"✅ Списано {amount} у [id{target_id}|{name}].")

# --- КОМАНДА: СВЯЗАТЬ КАРТОЧКУ ---
@labeler.message(regex=r"^(?i)Связать\s+(.*)$")
async def link_card(message: Message, match):
    if message.from_id not in ADMIN_IDS: return

    full_text = match[0] 

    # Ищем ID фото
    photo_match = re.search(r"photo(-?\d+_\d+)", full_text)
    if not photo_match:
        return await message.answer("❌ Не вижу ссылку на фото (photo-XXX_YYY).")
    
    full_photo_id = photo_match.group(1)

    # Ищем пользователя
    target_id = None
    for word in full_text.split():
        uid = get_id_from_mention(word)
        if uid:
            target_id = uid
            break
    
    if not target_id:
        return await message.answer("❌ Ссылку вижу, а пользователя — нет.")

    # Сохраняем
    user = await User.get_or_none(vk_id=target_id)
    if not user:
        name = await get_name(message, target_id)
        user = await User.create(vk_id=target_id, first_name=name, last_name="Player")
    
    user.card_photo_id = full_photo_id
    # Сбрасываем старый ID комментария, так как фото новое
    user.card_comment_id = None 
    await user.save()
    
    # Создаем первый комментарий
    await message.answer(f"🔗 Связано! Пробую оставить комментарий...")
    await auto_update_card(message.ctx_api, user)

# --- ОСТАЛЬНЫЕ КОМАНДЫ (БАН, РАЗБАН, РАССЫЛКА, ПРОМО, СТОИМОСТЬ) ---
# ... (Они не менялись, но чтобы файл был полным, я включу их ниже) ...

@labeler.message(regex=r"^(?i)Попущенный\s+(.*?)(?:\s+(.*))?$")
async def admin_ban(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    target_raw = match[0]
    reason = match[1] or "Без причины"
    target_id = get_id_from_mention(target_raw)
    if not target_id: return await message.answer("❌ Кого?")
    user = await User.get_or_none(vk_id=target_id)
    if not user: return 
    user.is_banned = True
    await user.save()
    await message.answer(f"⛔ Забанен [id{target_id}|User]. Причина: {reason}")

@labeler.message(regex=r"^(?i)Разбан\s+(.*?)$")
async def admin_unban(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    target_id = get_id_from_mention(match[0])
    if not target_id: return
    user = await User.get_or_none(vk_id=target_id)
    if user:
        user.is_banned = False
        await user.save()
        await message.answer("✅ Разбанен.")

@labeler.message(regex=r"^(?i)Рассылка\s+(.*)$")
async def admin_broadcast(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    text = match[0]
    users = await User.all()
    await message.answer(f"📢 Рассылка на {len(users)} человек.")
    for user in users:
        try:
            await message.ctx_api.messages.send(peer_id=user.vk_id, message=f"📢 {text}", random_id=0)
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
    reply_text = message.reply_message.text
    user_match = re.search(r"\[id(\d+)\|", reply_text)
    req_match = re.search(r"ЗАЯВКА №(\d+)", reply_text)
    if user_match:
        target_id = int(user_match.group(1))
        if req_match:
            req = await ShopRequest.get_or_none(id=int(req_match.group(1)))
            if req:
                req.price = price
                req.status = RequestStatus.PRICE_SET
                await req.save()
        try:
            await message.ctx_api.messages.send(peer_id=target_id, message=f"💰 Твой заказ оценен в {price} чилликов!", random_id=0)
            await message.answer("✅ Оценено.")
        except:
            await message.answer("⚠ Оценено, но ЛС закрыто.")
