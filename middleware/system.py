from vkbottle import BaseMiddleware
from vkbottle.bot import Message
from database.models import User
import time
import re
from settings import RATE_LIMIT_SECONDS, STARTING_BALANCE, VK_GROUP_ID

user_last_msg = {}

class SystemMiddleware(BaseMiddleware[Message]):
    async def pre(self):
        if self.event.from_id < 0:
            self.stop("Group message")
            return

        text = self.event.text
        
        # 1. ЧИСТКА ОТ УПОМИНАНИЙ (ТЕГОВ)
        if VK_GROUP_ID > 0:
            # Убираем [club123|...] и @club123
            patterns = [
                rf"\[(?:club|public){VK_GROUP_ID}\|.*?\]",
                rf"\[id{VK_GROUP_ID}\|.*?\]", # На случай, если бот - страница
                rf"@(?:club|public){VK_GROUP_ID}"
            ]
            for pat in patterns:
                text = re.sub(pat, "", text, flags=re.IGNORECASE)

        # 2. ЧИСТКА ОТ ЭМОДЗИ И СИМВОЛОВ В НАЧАЛЕ (ДЛЯ КНОПОК)
        # Удаляем всё, что НЕ является буквой (рус/англ) или цифрой в начале строки
        # Это удалит "💰 ", "👤 ", "!!! ", ">>> " и прочее перед командой
        # Но оставит саму команду
        match = re.search(r"^\s*([^\w\s]+)?\s*(.*)", text, flags=re.DOTALL)
        if match:
            # Если нашли мусор в начале - берем чистый текст
            # Группа 2 - это текст после символов
            cleaned_text = match.group(2)
            # Если текст не пустой, используем его. Иначе оставляем оригинал (вдруг это смайл-команда)
            if cleaned_text:
                text = cleaned_text.strip()
            else:
                text = text.strip()

        self.event.text = text

        user_id = self.event.from_id
        
        # 3. Throttling (Анти-спам)
        now = time.time()
        last_time = user_last_msg.get(user_id, 0)
        if now - last_time < RATE_LIMIT_SECONDS:
            self.stop("Throttled")
            return
        user_last_msg[user_id] = now

        # 4. Авто-регистрация
        user = await User.get_or_none(vk_id=user_id)
        
        if not user:
            first_name = "Неизвестный"
            last_name = "Игрок"
            try:
                user_infos = await self.event.ctx_api.users.get(user_id)
                if user_infos:
                    first_name = user_infos[0].first_name
                    last_name = user_infos[0].last_name
            except Exception as e:
                print(f"⚠️ Ошибка имени: {e}")

            user = await User.create(
                vk_id=user_id,
                first_name=first_name,
                last_name=last_name,
                balance=STARTING_BALANCE
            )

        if user.is_banned:
            self.stop("Banned user")
            return

        self.send({"user_db": user})
