from vkbottle import Keyboard, KeyboardButtonColor, Text
from database.models import User, SystemConfig
from datetime import datetime, timezone, timedelta

async def get_smart_keyboard(user: User, menu_type: str = "main") -> str:
    """Генерирует JSON клавиатуры в зависимости от контекста."""
    kb = Keyboard(one_time=False, inline=False)
    
    # Статус ивента
    event_conf = await SystemConfig.get_or_none(key="event_new_year")
    is_event_active = event_conf and event_conf.value == "True"

    # Бонус
    bonus_label = "🎁 Бонус"
    bonus_color = KeyboardButtonColor.POSITIVE
    if user.last_bonus:
        now = datetime.now(timezone.utc)
        diff = now - user.last_bonus
        if diff < timedelta(hours=24):
            remaining = timedelta(hours=24) - diff
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            bonus_label = f"⏳ {hours}ч {minutes}м"
            bonus_color = KeyboardButtonColor.SECONDARY

    # --- СБОРКА ---
    if menu_type == "profile":
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

    elif menu_type == "main": # Для команды Баланс
        kb.add(Text("👤 Профиль"), color=KeyboardButtonColor.PRIMARY)
        kb.add(Text("🎒 Инвентарь"), color=KeyboardButtonColor.PRIMARY)
        kb.row()
        if is_event_active:
            kb.add(Text("🎄 Подарки", payload={"cmd": "open_menu"}), color=KeyboardButtonColor.POSITIVE)
            kb.row()
        kb.add(Text(bonus_label), color=bonus_color)
        kb.add(Text("🛒 Магазин"), color=KeyboardButtonColor.PRIMARY)
        kb.add(Text("📚 Помощь"), color=KeyboardButtonColor.SECONDARY)

    elif menu_type == "help":
        kb.add(Text("👤 Профиль"), color=KeyboardButtonColor.PRIMARY)
        kb.add(Text("🎒 Инвентарь"), color=KeyboardButtonColor.PRIMARY)
        kb.row()
        kb.add(Text(bonus_label), color=bonus_color)
        kb.add(Text("🛒 Магазин"), color=KeyboardButtonColor.PRIMARY)

    return kb.get_json()

async def get_image_for_command(cmd_name: str) -> str | None:
    key = f"img_{cmd_name}"
    conf = await SystemConfig.get_or_none(key=key)
    return conf.value if conf else None
