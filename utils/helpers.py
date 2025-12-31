import re
import shortuuid
import json
import urllib.parse


def get_id_from_mention(text: str) -> int | None:
    """
    Извлекает ID пользователя из упоминания или ссылки.
    
    Поддерживаемые форматы:
    - [id123|@username]
    - vk.com/id123
    - https://vk.com/id123
    
    Args:
        text: Текст с упоминанием или ссылкой
        
    Returns:
        int | None: ID пользователя или None
    """
    # Паттерн для упоминания [id123|...]
    mention_pattern = r"\[id(\d+)\|.*?\]"
    
    # Паттерн для ссылки vk.com/id123
    link_pattern = r"(?:https?://)?vk\.com/id(\d+)"
    
    # Проверяем упоминание
    match_mention = re.search(mention_pattern, text)
    if match_mention:
        return int(match_mention.group(1))
    
    # Проверяем ссылку
    match_link = re.search(link_pattern, text)
    if match_link:
        return int(match_link.group(1))
    
    return None


def generate_cheque_code() -> str:
    """
    Генерирует уникальный код для чека.
    
    Returns:
        str: Код из 6 символов (буквы и цифры)
    """
    return shortuuid.ShortUUID().random(length=6).upper()


def get_chart_url(labels: list, data: list, title: str) -> str:
    """
    Генерирует URL для графика с использованием QuickChart.io
    
    Args:
        labels: Подписи для оси X
        data: Данные для графика
        title: Заголовок графика
        
    Returns:
        str: URL картинки с графиком
    """
    base = "https://quickchart.io/chart?c="
    
    config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Чиллики",
                    "data": data,
                    "fill": False,
                    "borderColor": "rgb(255, 99, 132)",
                    "backgroundColor": "rgba(255, 99, 132, 0.5)",
                    "tension": 0.1
                }
            ]
        },
        "options": {
            "title": {
                "display": True,
                "text": title,
                "fontSize": 16
            },
            "legend": {
                "display": False
            },
            "scales": {
                "y": {
                    "beginAtZero": True
                }
            }
        }
    }
    
    return base + urllib.parse.quote(json.dumps(config))


def format_number(num: int) -> str:
    """
    Форматирует число с разделителями тысяч.
    
    Args:
        num: Число для форматирования
        
    Returns:
        str: Отформатированное число (1000 -> "1,000")
    """
    return f"{num:,}"


def get_rank_emoji(balance: int) -> str:
    """
    Возвращает эмодзи ранга в зависимости от баланса.
    
    Args:
        balance: Баланс игрока
        
    Returns:
        str: Эмодзи ранга
    """
    if balance < 500:
        return "🦠"  # Амеба
    elif balance < 1000:
        return "🗑"  # Биомусор
    elif balance < 5000:
        return "🤡"  # Попущ
    elif balance < 20000:
        return "🚽"  # Говночист
    elif balance < 50000:
        return "🐀"  # Крыса
    elif balance < 100000:
        return "🐒"  # Скам-мамонт
    elif balance < 500000:
        return "👺"  # Душнила
    elif balance < 1000000:
        return "💊"  # Шизоид
    else:
        return "👑"  # Папик


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Обрезает текст до указанной длины с добавлением "..."
    
    Args:
        text: Текст для обрезки
        max_length: Максимальная длина
        
    Returns:
        str: Обрезанный текст
    """
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."
