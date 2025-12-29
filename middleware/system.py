from vkbottle import BaseMiddleware
from vkbottle.bot import Message
from database.models import User
import time
import re
from settings import RATE_LIMIT_SECONDS, STARTING_BALANCE, VK_GROUP_ID

user_last_msg = {}

class SystemMiddleware(BaseMiddleware[Message]):
    async def pre(self):
        # Игнорируем сообщения от групп (отрицательный ID)
        if self.event.from_id < 0:
            self.stop("Group message")
            return

        # --- ФИКС ДЛЯ @chiill_rp (club224755876) ---
        # Убираем упоминание бота из начала сообщения
        if VK_GROUP_ID > 0:
            # Паттерны для поиска упоминаний:
            # 1. [club224755876|@chiill_rp] или [club224755876|текст]
            # 2. [public224755876|@chiill_rp] или [public224755876|текст]
            # 3. @club224755876 (короткая запись)
            patterns = [
                rf"^\[club{VK_GROUP_ID}\|.*?\]\s*",  # [club224755876|...]
                rf"^\[public{VK_GROUP_ID}\|.*?\]\s*",  # [public224755876|...]
                rf"^@club{VK_GROUP_ID}\s*",  # @club224755876
                rf"^@public{VK_GROUP_ID}\s*",  # @public224755876
            ]
            
            # Проверяем все паттерны
            for pattern in patterns:
                if re.match(pattern, self.event.text, re.IGNORECASE):
                    # Удаляем упоминание из текста
                    self.event.text = re.sub(pattern, "", self.event.text, flags=re.IGNORECASE).strip()
                    break
        
        # Также обрабатываем случай, когда бот упоминается в середине текста
        # (например, пересланное сообщение или ответ)
        if VK_GROUP_ID > 0:
            # Удаляем упоминания бота из любого места текста
            self.event.text = re.sub(
                rf"\[(?:club|public){VK_GROUP_ID}\|.*?\]",
                "",
                self.event.text,
                flags=re.IGNORECASE
            ).strip()
        # -------------------------------------------

        user_id = self.event.from_id
        
        # 1. Throttling (Анти-спам)
        now = time.time()
        last_time = user_last_msg.get(user_id, 0)
        if now - last_time < RATE_LIMIT_SECONDS:
            self.stop("Throttled")
            return
        user_last_msg[user_id] = now

        # 2. Авто-регистрация
        user = await User.get_or_none(vk_id=user_id)
        
        if not user:
            first_name = "Неизвестный"
            last_name = "Игрок"
            try:
                # Получаем инфо, если профиль открыт
                user_infos = await self.event.ctx_api.users.get(user_id)
                if user_infos:
                    first_name = user_infos[0].first_name
                    last_name = user_infos[0].last_name
            except Exception as e:
                print(f"⚠️ Не удалось получить имя для {user_id}: {e}")

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
