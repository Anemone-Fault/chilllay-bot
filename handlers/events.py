from vkbottle.bot import BotLabeler, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from database.models import User, Item, Inventory, GiftBox, Rarity, GiftType, ItemType, SystemConfig
from utils.keyboards import get_smart_keyboard
from settings import GIFT_IMAGES, ADMIN_IDS
from utils.card_updater import auto_update_card
import random
import asyncio

labeler = BotLabeler()


# ====================
# 🎒 ИНВЕНТАРЬ
# ====================

@labeler.message(regex=r"^(?i)(?:Инвентарь|Сумка|Inventory|🎒 Инвентарь)$")
async def show_inventory(message: Message):
    user_db = await User.get(vk_id=message.from_id)
    inv_items = await Inventory.filter(user=user_db).prefetch_related("item").all()
    gifts = await GiftBox.filter(user=user_db, quantity__gt=0).all()

    text = (
        f"╔═════════════════════╗\n"
        f"║   🎒 РЮКЗАК БАРАХЛА  ║\n"
        f"╚═════════════════════╝\n\n"
    )

    # Проверка на пустоту
    if not inv_items and not gifts:
        text += (
            "🕸️ Тут паутина и пустота...\n\n"
            "Где твои вещи, бомж? 🤡\n\n"
            "{'─' * 25}\n\n"
            "💡 КАК ПОЛУЧИТЬ ПРЕДМЕТЫ:\n\n"
            "• Пиши РП-посты (за них\n"
            "  выпадают кейсы)\n\n"
            "• Лайкай посты группы\n"
            "  (20% шанс кейса)\n\n"
            "• Участвуй в ивентах\n\n"
            "Иди работай, лентяй! 🦥"
        )
        return await message.answer(text, keyboard=await get_smart_keyboard(user_db, "main"))

    # Кейсы
    if gifts:
        text += "┌─ 🎁 КЕЙСЫ\n│\n"
        
        total_boxes = sum(g.quantity for g in gifts)
        text += f"│  Всего: {total_boxes} шт.\n│\n"
        
        for g in gifts:
            rarity_emoji = {
                Rarity.COMMON: "⚪",
                Rarity.RARE: "🔵",
                Rarity.EPIC: "🟣",
                Rarity.CHILL: "🟡"
            }.get(g.rarity, "⚫")
            
            type_emoji = {
                GiftType.MONEY: "💰",
                GiftType.ITEM: "📦",
                GiftType.TALENT: "✨",
                GiftType.LUCKY: "🍀",
                GiftType.FATE: "🔮"
            }.get(g.gift_type, "🎁")
            
            text += f"├─ {type_emoji} {g.gift_type.value}\n"
            text += f"│  └─ {rarity_emoji} {g.rarity.value} × {g.quantity}\n"
        
        text += "│\n"
        text += f"└─ {'─' * 21}\n\n"

    # Предметы
    if inv_items:
        text += "┌─ 📦 ПРЕДМЕТЫ\n│\n"
        
        total_items = sum(slot.quantity for slot in inv_items)
        text += f"│  Всего: {total_items} шт.\n│\n"
        
        for slot in inv_items:
            type_emoji = {
                ItemType.ITEM: "⚔️",
                ItemType.TALENT: "✨",
                ItemType.ABILITY: "🔮"
            }.get(slot.item.type, "📦")
            
            rarity_emoji = {
                Rarity.COMMON: "⚪",
                Rarity.RARE: "🔵",
                Rarity.EPIC: "🟣",
                Rarity.CHILL: "🟡"
            }.get(slot.item.rarity, "⚫")
            
            text += f"├─ {type_emoji} {slot.item.name}\n"
            text += f"│  ├─ {rarity_emoji} {slot.item.rarity.value}\n"
            text += f"│  └─ Количество: {slot.quantity} шт.\n"
        
        text += "│\n"
        text += f"└─ {'─' * 21}\n"
    
    # Кнопка открытия
    kb = Keyboard(inline=True)
    if gifts:
        kb.add(
            Text("🎁 Открыть кейс", payload={"cmd": "open_menu"}),
            color=KeyboardButtonColor.POSITIVE
        )
        kb.row()
    
    kb.add(Text("🔄 Обновить"), color=KeyboardButtonColor.PRIMARY)
    
    await message.answer(text, keyboard=kb.get_json())


# ====================
# 🎁 МЕНЮ ВЫБОРА КЕЙСА
# ====================

@labeler.message(payload_map={"cmd": "open_menu"})
async def open_gift_menu(message: Message):
    user_db = await User.get(vk_id=message.from_id)
    gifts = await GiftBox.filter(user=user_db, quantity__gt=0).all()
    
    if not gifts:
        return await message.answer(
            "╔═════════════════════╗\n"
            "║  😔 КЕЙСОВ НЕТ!      ║\n"
            "╚═════════════════════╝\n\n"
            "У тебя нет подарков!\n\n"
            "Иди фарми РП-посты,\n"
            "нищеброд! 🦝",
            ephemeral=True
        )
    
    text = (
        "╔═════════════════════╗\n"
        "║  🎁 ВЫБЕРИ КЕЙС      ║\n"
        "╚═════════════════════╝\n\n"
        "Какой подарок откроем?\n\n"
    )
    
    kb = Keyboard(inline=True)
    
    for g in gifts:
        rarity_emoji = {
            Rarity.COMMON: "⚪",
            Rarity.RARE: "🔵",
            Rarity.EPIC: "🟣",
            Rarity.CHILL: "🟡"
        }.get(g.rarity, "⚫")
        
        type_emoji = {
            GiftType.MONEY: "💰",
            GiftType.ITEM: "📦",
            GiftType.TALENT: "✨",
            GiftType.LUCKY: "🍀",
            GiftType.FATE: "🔮"
        }.get(g.gift_type, "🎁")
        
        button_text = f"{type_emoji} {g.gift_type.value} {rarity_emoji} ({g.quantity})"
        
        kb.add(
            Text(
                button_text,
                payload={
                    "cmd": "open_anim",
                    "rarity": g.rarity.value,
                    "type": g.gift_type.value
                }
            ),
            color=KeyboardButtonColor.POSITIVE
        )
        kb.row()
        
    await message.answer(text, keyboard=kb.get_json())


# ====================
# 🎰 АНИМАЦИЯ ОТКРЫТИЯ КЕЙСА
# ====================

@labeler.message(payload_map={"cmd": "open_anim"})
async def open_gift_process(message: Message):
    user_db = await User.get(vk_id=message.from_id)
    payload = message.get_payload_json()
    r_val = payload.get("rarity")
    t_val = payload.get("type")

    # Проверка наличия кейса
    box = await GiftBox.filter(user=user_db, rarity=r_val, gift_type=t_val).first()
    if not box or box.quantity < 1:
        return await message.answer(
            "╔═════════════════════╗\n"
            "║  ❌ КЕЙСА НЕТ!       ║\n"
            "╚═════════════════════╝\n\n"
            "Такой коробки нет!\n"
            "Кто-то её украл? 🤔",
            ephemeral=True
        )

    # Картинка кейса
    box_image = GIFT_IMAGES.get(t_val)
    
    # Анимация открытия
    wait_msg = await message.answer(
        f"╔═════════════════════╗\n"
        f"║  🎁 ОТКРЫВАЮ КЕЙС... ║\n"
        f"╚═════════════════════╝\n\n"
        f"┌─ ИНФОРМАЦИЯ\n"
        f"│\n"
        f"├─ Тип: {t_val}\n"
        f"├─ Редкость: {r_val}\n"
        f"│\n"
        f"└─ {'─' * 21}\n\n"
        f"⏳ Распаковка...\n"
        f"[{'░' * 10}] 0%",
        attachment=box_image
    )
    
    # Прогресс-бар анимация
    for i in range(1, 6):
        await asyncio.sleep(0.4)
        progress = i * 20
        filled = i * 2
        bar = f"[{'█' * filled}{'░' * (10 - filled)}] {progress}%"
        
        try:
            await message.ctx_api.messages.edit(
                peer_id=message.peer_id,
                message=(
                    f"╔═════════════════════╗\n"
                    f"║  🎁 ОТКРЫВАЮ КЕЙС... ║\n"
                    f"╚═════════════════════╝\n\n"
                    f"┌─ ИНФОРМАЦИЯ\n"
                    f"│\n"
                    f"├─ Тип: {t_val}\n"
                    f"├─ Редкость: {r_val}\n"
                    f"│\n"
                    f"└─ {'─' * 21}\n\n"
                    f"⏳ Распаковка...\n"
                    f"{bar}"
                ),
                conversation_message_id=wait_msg.conversation_message_id,
                attachment=box_image
            )
        except:
            pass

    await asyncio.sleep(0.5)

    # Логика выдачи
    amount = 0
    won_item = None
    pool = []

    if box.gift_type == GiftType.MONEY:
        # Выдача денег
        ranges = {
            Rarity.COMMON: (10, 500),
            Rarity.RARE: (500, 2000),
            Rarity.EPIC: (2000, 5000),
            Rarity.CHILL: (5000, 10000)
        }
        mn, mx = ranges.get(box.rarity, (10, 100))
        amount = random.randint(mn, mx)
        
        user_db.balance += amount
        await user_db.save()
        await auto_update_card(message.ctx_api, user_db)

    elif box.gift_type in [GiftType.ITEM, GiftType.TALENT, GiftType.LUCKY]:
        # Выдача предмета
        target_type = ItemType.ITEM
        if box.gift_type == GiftType.TALENT:
            target_type = ItemType.TALENT
        elif box.gift_type == GiftType.LUCKY:
            target_type = ItemType.ABILITY
        
        pool = await Item.filter(type=target_type, rarity=box.rarity).all()
        if not pool:
            pool = await Item.filter(type=target_type).all()
        
        if pool:
            won_item = random.choice(pool)
            inv, _ = await Inventory.get_or_create(user=user_db, item=won_item)
            inv.quantity += 1
            await inv.save()
            
            # Если у предмета есть фото, используем его
            if won_item.photo_id:
                box_image = won_item.photo_id

    # Удаляем кейс
    box.quantity -= 1
    if box.quantity <= 0:
        await box.delete()
    else:
        await box.save()

    # Формируем результат
    header = "🎉 КЕЙС ОТКРЫТ!"
    if box.gift_type == GiftType.FATE:
        header = "🔮 СУДЬБОНОСНОЕ!"
    
    final_text = (
        f"╔═════════════════════╗\n"
        f"║  {header:^19}  ║\n"
        f"╚═════════════════════╝\n\n"
    )

    if box.gift_type == GiftType.MONEY:
        # Результат денег
        final_text += (
            f"┌─ 💰 ПОЛУЧЕНО\n"
            f"│\n"
            f"├─ Чилликов: {amount:,}₽\n"
            f"├─ Редкость: {r_val}\n"
            f"│\n"
            f"└─ {'─' * 21}\n\n"
            f"{'═' * 25}\n\n"
            f"📊 Баланс: {user_db.balance:,}₽\n\n"
            f"Красавчик! Проебешь? 💸"
        )
        
    elif box.gift_type == GiftType.FATE:
        # Судьбоносный кейс
        final_text += (
            f"⚡ СУДЬБОНОСНОЕ СОБЫТИЕ!\n\n"
            f"🔮 Боги обратили на тебя\n"
            f"   внимание!\n\n"
            f"Администрация уведомлена.\n"
            f"Жди своей награды... 👑\n\n"
            f"{'═' * 25}\n\n"
            f"Удача на твоей стороне! ✨"
        )
        
        # Уведомляем админов
        for admin_id in ADMIN_IDS:
            try:
                await message.ctx_api.messages.send(
                    peer_id=admin_id,
                    message=(
                        f"╔═════════════════════╗\n"
                        f"║  🚨 СУДЬБОНОСНОЕ!    ║\n"
                        f"╚═════════════════════╝\n\n"
                        f"👤 Игрок: {user_db.first_name}\n"
                        f"🆔 ID: {user_db.vk_id}\n\n"
                        f"🔮 Выбил судьбоносный\n"
                        f"   кейс!\n\n"
                        f"Подари ему что-то\n"
                        f"эпическое! 🎁"
                    ),
                    random_id=0
                )
            except:
                pass
                
    else:
        # Результат предмета
        if won_item:
            rarity_emoji = {
                Rarity.COMMON: "⚪",
                Rarity.RARE: "🔵",
                Rarity.EPIC: "🟣",
                Rarity.CHILL: "🟡"
            }.get(won_item.rarity, "⚫")
            
            type_emoji = {
                ItemType.ITEM: "⚔️",
                ItemType.TALENT: "✨",
                ItemType.ABILITY: "🔮"
            }.get(won_item.type, "📦")
            
            final_text += (
                f"┌─ {type_emoji} ПРЕДМЕТ ПОЛУЧЕН\n"
                f"│\n"
                f"├─ Название:\n"
                f"│  └─ {won_item.name}\n"
                f"│\n"
                f"├─ Редкость:\n"
                f"│  └─ {rarity_emoji} {won_item.rarity.value}\n"
                f"│\n"
                f"├─ Тип:\n"
                f"│  └─ {won_item.type.value}\n"
                f"│\n"
                f"└─ {'─' * 21}\n\n"
                f"{'═' * 25}\n\n"
                f"📦 Сохранено в инвентарь!\n\n"
                f"Не потеряй, лох! 🎒"
            )
        else:
            final_text += (
                f"💨 ПУСТОТА!\n\n"
                f"В кейсе ничего не было...\n"
                f"База предметов пуста! 🕸️\n\n"
                f"{'═' * 25}\n\n"
                f"Админы забыли добавить\n"
                f"предметы в базу! 🤡\n\n"
                f"Попроси их исправить это:\n"
                f"!Создать [имя] [ранг] [тип]"
            )

    # Отправляем результат
    try:
        await message.ctx_api.messages.edit(
            peer_id=message.peer_id,
            message=final_text,
            conversation_message_id=wait_msg.conversation_message_id,
            attachment=box_image,
            keyboard=None
        )
    except:
        await message.answer(final_text, attachment=box_image)


# ====================
# 🎭 ПЕРСОНАЖИ (ЗАГЛУШКА)
# ====================

@labeler.message(regex=r"^(?i)(?:Персонажи|Characters|🎭 Персонажи)$")
async def show_chars_placeholder(message: Message):
    await message.answer(
        "╔═════════════════════╗\n"
        "║  🚧 В РАЗРАБОТКЕ     ║\n"
        "╚═════════════════════╝\n\n"
        "🎭 Раздел персонажей\n"
        "   находится в стадии\n"
        "   разработки!\n\n"
        "Скоро здесь появится:\n"
        "• Создание персонажей\n"
        "• Карточки персонажей\n"
        "• Навыки и способности\n"
        "• Система прокачки\n\n"
        "{'═' * 25}\n\n"
        "⏳ Ожидайте обновления!\n\n"
        "P.S. Терпение, нищеброды! 🦝"
    )
