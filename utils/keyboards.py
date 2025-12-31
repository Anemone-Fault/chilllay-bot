from vkbottle import Keyboard, KeyboardButtonColor, Text
from database.models import User, SystemConfig
from datetime import datetime, timezone, timedelta


async def get_smart_keyboard(user: User, menu_type: str = "main") -> str:
    """
    Генерирует JSON клавиатуры (INLINE - на сообщении).
    """
    kb = Keyboard(one_time=False, inline=True)
    
    # 1. Проверяем статус ивента
    event_conf = await SystemConfig.get_or_none(key="event_new_year")
    is_event_active = event_conf and event_conf.value == "True"

    # 2. Проверяем бонус и генерируем текст
    bonus_label = "🎁 Бонус"
    bonus_color = KeyboardButtonColor.POSITIVE
    
    if user.last_bonus:
        now = datetime.now(timezone.utc)
        diff = now - user.last_bonus
        if diff < timedelta(hours=24):
            remaining = timedelta(hours=24) - diff
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            
            # Прогресс в эмодзи
            progress_percent = int((diff.total_seconds() / (24 * 3600)) * 100)
            if progress_percent < 25:
                bonus_label = f"⏳ {hours}ч {minutes}м"
            elif progress_percent < 50:
                bonus_label = f"⏰ {hours}ч {minutes}м"
            elif progress_percent < 75:
                bonus_label = f"⌛ {hours}ч {minutes}м"
            else:
                bonus_label = f"⏱ {hours}ч {minutes}м"
            
            bonus_color = KeyboardButtonColor.SECONDARY

    # 3. Сборка клавиатуры по типу меню
    if menu_type == "profile":
        # Меню профиля
        kb.add(Text("🎭 Персонажи"), color=KeyboardButtonColor.PRIMARY)
        kb.add(Text("🎒 Инвентарь"), color=KeyboardButtonColor.PRIMARY)
        kb.row()
        
        if is_event_active:
            kb.add(Text("🎄 Подарки", payload={"cmd": "open_menu"}), color=KeyboardButtonColor.POSITIVE)
            kb.row()
        
        kb.add(Text(bonus_label), color=bonus_color)
        kb.add(Text("🛒 Магазин"), color=KeyboardButtonColor.PRIMARY)
        kb.row()
        kb.add(Text("📚 Помощь"), color=KeyboardButtonColor.SECONDARY)

    elif menu_type == "main":
        # Главное меню (для баланса и других команд)
        kb.add(Text("👤 Профиль"), color=KeyboardButtonColor.PRIMARY)
        kb.add(Text("🎒 Инвентарь"), color=KeyboardButtonColor.PRIMARY)
        kb.row()
        
        if is_event_active:
            kb.add(Text("🎄 Подарки", payload={"cmd": "open_menu"}), color=KeyboardButtonColor.POSITIVE)
            kb.row()
        
        kb.add(Text(bonus_label), color=bonus_color)
        kb.add(Text("🛒 Магазин"), color=KeyboardButtonColor.PRIMARY)
        kb.row()
        kb.add(Text("📚 Помощь"), color=KeyboardButtonColor.SECONDARY)

    elif menu_type == "help":
        # Меню помощи
        kb.add(Text("👤 Профиль"), color=KeyboardButtonColor.PRIMARY)
        kb.add(Text("🎒 Инвентарь"), color=KeyboardButtonColor.PRIMARY)
        kb.row()
        
        if is_event_active:
            kb.add(Text("🎄 Подарки", payload={"cmd": "open_menu"}), color=KeyboardButtonColor.POSITIVE)
            kb.row()
        
        kb.add(Text(bonus_label), color=bonus_color)
        kb.add(Text("🛒 Магазин"), color=KeyboardButtonColor.PRIMARY)
        kb.row()
        kb.add(Text("💰 Баланс"), color=KeyboardButtonColor.SECONDARY)

    return kb.get_json()


async def get_image_for_command(cmd_name: str) -> str | None:
    """
    Получает изображение для команды из базы данных.
    """
    key = f"img_{cmd_name}"
    conf = await SystemConfig.get_or_none(key=key)
    return conf.value if conf else None
