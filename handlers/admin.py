from vkbottle.bot import BotLabeler, Message
from database.models import User, SystemConfig, Item, Rarity, ItemType, GiftBox, GiftType, Promo, ShopRequest, RequestStatus
from settings import ADMIN_IDS, MAIN_CHAT_ID
from utils.helpers import get_id_from_mention
from utils.card_updater import auto_update_card
import re

labeler = BotLabeler()

# --- ⚙️ УПРАВЛЕНИЕ ИВЕНТОМ ---
@labeler.message(regex=r"^!Ивент\s+(.*?)\s+(вкл|выкл)$")
async def toggle_event(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    
    event_name = match[0] # Например "НовыйГод"
    state = "True" if match[1].lower() == "вкл" else "False"
    
    key = f"event_{event_name.lower()}"
    conf, _ = await SystemConfig.get_or_create(key=key)
    conf.value = state
    await conf.save()
    
    await message.answer(f"⚙️ Ивент '{event_name}' установлен в {state}.")
    
    if MAIN_CHAT_ID != 0:
        if state == "True":
            announcement = (
                f"╔═══════════════╗\n"
                f"   🎄 {event_name.upper()}\n"
                f"╚═══════════════╝\n\n"
                f"✨ Событие официально запущено!\n"
                f"Получайте кейсы за РП и лайки.\n\n"
                f"🎁 В меню появилась кнопка «Подарки».\n"
                f"@all"
            )
        else:
            announcement = (
                f"╔═══════════════╗\n"
                f"   🏁 ИВЕНТ ЗАВЕРШЕН\n"
                f"╚═══════════════╝\n\n"
                f"Выдача кейсов остановлена.\n"
                f"Инвентарь и открытие по-прежнему работают.\n"
                f"@all"
            )
        try: await message.ctx_api.messages.send(peer_id=MAIN_CHAT_ID, message=announcement, random_id=0)
        except: pass

@labeler.message(regex=r"^!СетФото\s+(.*?)$")
async def set_cmd_photo(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    cmd = match[0].lower()
    if not message.attachments or message.attachments[0].type != "photo":
        return await message.answer("❌ Прикрепи фото к команде.")
    
    photo = message.attachments[0].photo
    photo_id = f"photo{photo.owner_id}_{photo.id}"
    
    key = f"img_{cmd}"
    conf, _ = await SystemConfig.get_or_create(key=key)
    conf.value = photo_id
    await conf.save()
    await message.answer(f"✅ Картинка для '{cmd}' сохранена!")

@labeler.message(regex=r"^!Создать\s+(.*?)\s+(.*?)\s+(.*?)$")
async def create_item_cmd(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    name, r_str, t_str = match[0], match[1], match[2]
    try:
        r = Rarity(r_str); t = ItemType(t_str)
        item = await Item.create(name=name, rarity=r, type=t)
        await message.answer(f"✅ Предмет {name} (ID {item.id}) создан.")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

@labeler.message(regex=r"^!Выдать\s+(.*?)(?:\s+(.*))?$")
async def admin_give_box(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    user_id = get_id_from_mention(match[0])
    if not user_id: return
    user = await User.get(vk_id=user_id)
    box = await GiftBox.create(user=user, rarity=Rarity.RARE, gift_type=GiftType.ITEM, quantity=1)
    await message.answer(f"✅ Кейс выдан {user.first_name}")

# --- СТАРЫЕ АДМИН КОМАНДЫ ---

@labeler.message(regex=r"^(?i)Начислить\s+(.*?)\s+(\d+)$")
async def admin_give_money(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    target_id = get_id_from_mention(match[0])
    amount = int(match[1])
    if not target_id: return
    user = await User.get_or_create(vk_id=target_id, defaults={"first_name": "Player", "last_name": "Player"})
    user[0].balance += amount
    await user[0].save()
    await auto_update_card(message.ctx_api, user[0])
    await message.answer(f"✅ +{amount}")

@labeler.message(regex=r"^(?i)Связать\s+(.*)$")
async def link_card(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    full_text = match[0]
    
    # Регулярка теперь ищет "photo-123_456" в любом месте текста
    # (в ссылке, в тексте, в упоминании [photo-123_456|...])
    photo_match = re.search(r"photo(-?\d+_\d+)", full_text)
    
    if not photo_match: 
        return await message.answer(
            "❌ Не вижу ID фото в тексте.\n"
            "Пример: Связать photo-123_456 @user\n"
            "Или: Связать vk.com/photo-123_456 @user"
        )
    
    target_id = None
    for word in full_text.split():
        uid = get_id_from_mention(word)
        if uid: target_id = uid; break
    
    if not target_id: return await message.answer("❌ Кому вязать?")
    
    user = await User.get(vk_id=target_id)
    # Сохраняем только часть "-123_456"
    user.card_photo_id = photo_match.group(1)
    await user.save()
    
    await message.answer("✅ Связано! Пробую обновить...")
    await auto_update_card(message.ctx_api, user)

@labeler.message(text="!Принудительная зарплата")
async def force_salary_cmd(message: Message):
    if message.from_id not in ADMIN_IDS: return
    conf, _ = await SystemConfig.get_or_create(key="last_salary_month")
    conf.value = "RESET"
    await conf.save()
    await message.answer("✅ Метка сброшена. Жди час или перезагрузи бота.")

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
    req_match = re.search(r"ЗАЯВКА №(\d+)", message.reply_message.text)
    user_match = re.search(r"\[id(\d+)\|", message.reply_message.text)
    if req_match:
        req = await ShopRequest.get_or_none(id=int(req_match.group(1)))
        if req:
            req.price = price
            req.status = RequestStatus.PRICE_SET
            await req.save()
    if user_match:
        target_id = int(user_match.group(1))
        try: await message.ctx_api.messages.send(peer_id=target_id, message=f"💰 Оценка товара: {price}", random_id=0)
        except: pass
    await message.answer("✅ Оценено.")
    
@labeler.message(text="!id")
async def get_chat_id(message: Message):
    await message.answer(f"🆔 ID этого чата: {message.peer_id}")
