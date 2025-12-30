from vkbottle.bot import BotLabeler, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from database.models import User, Item, Inventory, GiftBox, Rarity, GiftType, ItemType, SystemConfig
from utils.keyboards import get_smart_keyboard
from settings import GIFT_IMAGES, ADMIN_IDS
from utils.card_updater import auto_update_card
import random
import asyncio

labeler = BotLabeler()

# ═══════════════════════════════════════════════════════
# 🎨 СТИЛЬНЫЕ РАМКИ
# ═══════════════════════════════════════════════════════

def create_header(title: str, icon: str = "✦") -> str:
    """Создает красивый заголовок"""
    line = "─" * 20
    return f"╭{line}╮\n│ {icon} {title.center(16)} {icon} │\n╰{line}╯"

# ═══════════════════════════════════════════════════════
# 🎒 КОМАНДА: ИНВЕНТАРЬ
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:🎒\s*)?(?:Инвентарь|Сумка|Inventory)$")
async def show_inventory(message: Message):
    user_db = await User.get(vk_id=message.from_id)
    inv_items = await Inventory.filter(user=user_db).prefetch_related("item").all()
    gifts = await GiftBox.filter(user=user_db, quantity__gt=0).all()

    header = create_header("РЮКЗАК", "🎒")
    text = header + "\n\n"

    # Пустой инвентарь
    if not inv_items and not gifts:
        text += (
            "  🕸 Здесь пусто как в голове...\n\n"
            "  💡 КАК ПОЛУЧИТЬ ПРЕДМЕТЫ:\n"
            "  • Пиши РП-посты в чате\n"
            "  • Ставь лайки на посты\n"
            "  • Открывай кейсы\n\n"
            "  🎁 За активность выпадают кейсы!\n"
        )
        return await message.answer(text, keyboard=await get_smart_keyboard(user_db, "main"))

    # Кейсы
    if gifts:
        text += "▸ КЕЙСЫ\n"
        rarity_icons = {
            Rarity.COMMON: "⚪",
            Rarity.RARE: "🔵",
            Rarity.EPIC: "🟣",
            Rarity.CHILL: "🌟"
        }
        
        for g in gifts:
            icon = rarity_icons.get(g.rarity, "📦")
            text += f"  {icon} {g.gift_type.value}\n"
            text += f"     ↳ {g.rarity.value} × {g.quantity} шт.\n"
        text += "\n"

    # Предметы
    if inv_items:
        text += "▸ КОЛЛЕКЦИЯ\n"
        type_icons = {
            ItemType.ITEM: "⚔️",
            ItemType.TALENT: "✨",
            ItemType.ABILITY: "🔮"
        }
        
        # Группируем по типам
        by_type = {}
        for slot in inv_items:
            item_type = slot.item.type
            if item_type not in by_type:
                by_type[item_type] = []
            by_type[item_type].append(slot)
        
        for item_type, items in by_type.items():
            type_icon = type_icons.get(item_type, "📦")
            type_name = item_type.value
            text += f"\n  {type_icon} {type_name.upper()}\n"
            
            for slot in items:
                rarity_badge = {"Обычный": "●", "Редкий": "◆", "Эпический": "★", "Чилловый": "✦"}
                badge = rarity_badge.get(slot.item.rarity.value, "●")
                text += f"     {badge} {slot.item.name} × {slot.quantity}\n"
    
    text += f"\n  📊 Всего предметов: {len(inv_items)}\n"
    text += f"  🎁 Всего кейсов: {sum(g.quantity for g in gifts)}\n"
    
    # Кнопки
    kb = Keyboard(inline=True)
    if gifts:
        kb.add(Text("🎁 Открыть кейс", payload={"cmd": "open_menu"}), color=KeyboardButtonColor.POSITIVE)
    
    await message.answer(text, keyboard=kb.get_json())


# ═══════════════════════════════════════════════════════
# 🎁 МЕНЮ ОТКРЫТИЯ КЕЙСОВ
# ═══════════════════════════════════════════════════════

@labeler.message(payload_map={"cmd": "open_menu"})
async def open_gift_menu(message: Message):
    user_db = await User.get(vk_id=message.from_id)
    gifts = await GiftBox.filter(user=user_db, quantity__gt=0).all()
    
    if not gifts:
        return await message.answer("❌ У тебя нет кейсов", ephemeral=True)
    
    header = create_header("ВЫБЕРИ КЕЙС", "🎁")
    text = header + "\n\n"
    
    # Группируем по редкости
    by_rarity = {}
    for g in gifts:
        if g.rarity not in by_rarity:
            by_rarity[g.rarity] = []
        by_rarity[g.rarity].append(g)
    
    rarity_order = [Rarity.COMMON, Rarity.RARE, Rarity.EPIC, Rarity.CHILL]
    rarity_icons = {
        Rarity.COMMON: "⚪",
        Rarity.RARE: "🔵",
        Rarity.EPIC: "🟣",
        Rarity.CHILL: "🌟"
    }
    
    kb = Keyboard(inline=True)
    
    for rarity in rarity_order:
        if rarity in by_rarity:
            text += f"\n{rarity_icons[rarity]} {rarity.value.upper()}\n"
            for g in by_rarity[rarity]:
                text += f"  • {g.gift_type.value} × {g.quantity}\n"
                kb.add(
                    Text(f"{g.gift_type.value} ({g.rarity.value})", 
                         payload={"cmd": "open_anim", "rarity": g.rarity.value, "type": g.gift_type.value}),
                    color=KeyboardButtonColor.POSITIVE
                )
                kb.row()
    
    text += "\n💡 Нажми на кнопку, чтобы открыть"
        
    await message.answer(text, keyboard=kb.get_json())


# ═══════════════════════════════════════════════════════
# 🎰 АНИМАЦИЯ ОТКРЫТИЯ КЕЙСА
# ═══════════════════════════════════════════════════════

@labeler.message(payload_map={"cmd": "open_anim"})
async def open_gift_process(message: Message):
    user_db = await User.get(vk_id=message.from_id)
    payload = message.get_payload_json()
    r_val = payload.get("rarity")
    t_val = payload.get("type")

    box = await GiftBox.filter(user=user_db, rarity=r_val, gift_type=t_val).first()
    if not box or box.quantity < 1:
        return await message.answer("❌ Такой коробки нет.")

    box_image = GIFT_IMAGES.get(t_val)
    
    # Анимация открытия
    frames = [
        "🎁 Трясем коробку...",
        "📦 Срываем упаковку...",
        "✨ Открываем...",
        "🎊 Что же внутри?..."
    ]
    
    wait_msg = await message.answer(frames[0], attachment=box_image)
    
    for frame in frames[1:]:
        await asyncio.sleep(0.8)
        try:
            await message.ctx_api.messages.edit(
                peer_id=message.peer_id,
                message=frame,
                conversation_message_id=wait_msg.conversation_message_id,
                attachment=box_image
            )
        except:
            pass
    
    await asyncio.sleep(0.5)

    # Логика дропа
    amount = 0
    won_item = None
    pool = []

    # Чилликовый кейс
    if box.gift_type == GiftType.MONEY:
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

    # Предметный кейс
    elif box.gift_type in [GiftType.ITEM, GiftType.TALENT, GiftType.LUCKY]:
        target_type = ItemType.ITEM
        if box.gift_type == GiftType.TALENT:
            target_type = ItemType.TALENT
        if box.gift_type == GiftType.LUCKY:
            target_type = ItemType.ABILITY
        
        # Сначала ищем по редкости, потом любые
        pool = await Item.filter(type=target_type, rarity=box.rarity).all()
        if not pool:
            pool = await Item.filter(type=target_type).all()
        
        if pool:
            won_item = random.choice(pool)
            inv, _ = await Inventory.get_or_create(user=user_db, item=won_item)
            inv.quantity += 1
            await inv.save()
            if won_item.photo_id:
                box_image = won_item.photo_id

    # Уменьшаем кейсы
    box.quantity -= 1
    if box.quantity <= 0:
        await box.delete()
    else:
        await box.save()

    # Финальное сообщение
    rarity_icons = {
        Rarity.COMMON: "⚪",
        Rarity.RARE: "🔵",
        Rarity.EPIC: "🟣",
        Rarity.CHILL: "🌟"
    }
    
    icon = rarity_icons.get(box.rarity, "🎁")
    header = create_header("ОТКРЫТО", icon)
    final_text = header + "\n\n"

    # Чилликовый дроп
    if box.gift_type == GiftType.MONEY:
        amount_formatted = f"{amount:,}".replace(",", " ")
        balance_formatted = f"{user_db.balance:,}".replace(",", " ")
        
        # Реакция на сумму
        reaction = "💰" if amount < 1000 else "💎" if amount < 5000 else "🤑"
        
        final_text += (
            f"  {reaction} Выпало: {amount_formatted} чилликов\n\n"
            f"  📊 Баланс: {balance_formatted} ₽\n"
        )
        
        if amount > 5000:
            final_text += "\n  🎉 Отличный дроп!\n"

    # Судьбоносный кейс
    elif box.gift_type == GiftType.FATE:
        final_text += (
            "  🔮 СУДЬБОНОСНОЕ СОБЫТИЕ!\n\n"
            "  ⚡ Администрация уведомлена\n"
            "  ↳ Ожидай особый приз...\n"
        )
        # Уведомляем админов
        for admin_id in ADMIN_IDS:
            try:
                await message.ctx_api.messages.send(
                    peer_id=admin_id,
                    message=(
                        f"{create_header('СУДЬБА', '🔮')}\n\n"
                        f"  👤 Игрок: {user_db.first_name}\n"
                        f"  🆔 ID: {user_db.vk_id}\n\n"
                        f"  Выбил судьбоносный кейс!\n"
                    ),
                    random_id=0
                )
            except:
                pass

    # Предметный дроп
    else:
        if won_item:
            type_icons = {
                ItemType.ITEM: "⚔️",
                ItemType.TALENT: "✨",
                ItemType.ABILITY: "🔮"
            }
            type_icon = type_icons.get(won_item.type, "📦")
            
            final_text += (
                f"  {type_icon} {won_item.name}\n"
                f"  ━━━━━━━━━━━━━━━\n"
                f"  • Ранг: {won_item.rarity.value}\n"
                f"  • Тип: {won_item.type.value}\n\n"
            )
            
            if won_item.description != "Описание от администрации":
                final_text += f"  📝 {won_item.description}\n\n"
            
            final_text += "  ✅ Сохранено в инвентарь!\n"
        else:
            final_text += (
                "  💨 Пусто...\n\n"
                "  База предметов для этого\n"
                "  типа кейса пока пуста.\n"
            )

    # Обновляем сообщение
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


# ═══════════════════════════════════════════════════════
# 🎭 КОМАНДА: ПЕРСОНАЖИ (ЗАГЛУШКА)
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:🎭\s*)?(?:Персонажи|Персы|Characters)$")
async def show_chars_placeholder(message: Message):
    header = create_header("ПЕРСОНАЖИ", "🎭")
    
    text = (
        f"{header}\n\n"
        f"  🚧 Раздел в разработке\n\n"
        f"  Скоро здесь появится:\n"
        f"  • Создание персонажей\n"
        f"  • Кастомизация внешности\n"
        f"  • Система характеристик\n"
        f"  • Инвентарь персонажа\n\n"
        f"  ⏳ Ожидайте обновления!\n"
    )
    
    await message.answer(text)
