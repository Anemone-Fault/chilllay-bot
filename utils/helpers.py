import re
import shortuuid
import json
import urllib.parse

def get_id_from_mention(text: str) -> int | None:
    mention_pattern = r"\[id(\d+)\|.*?\]"
    link_pattern = r"vk\.com/id(\d+)"
    
    match_mention = re.search(mention_pattern, text)
    if match_mention: return int(match_mention.group(1))
    
    match_link = re.search(link_pattern, text)
    if match_link: return int(match_link.group(1))
    return None

def generate_cheque_code() -> str:
    return shortuuid.ShortUUID().random(length=6)

def get_chart_url(labels: list, data: list, title: str) -> str:
    base = "https://quickchart.io/chart?c="
    config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [{"label": "Чиллики", "data": data, "fill": False, "borderColor": "red", "tension": 0.1}]
        },
        "options": {
            "title": {"display": True, "text": title},
            "legend": {"display": False}
        }
    }
    return base + urllib.parse.quote(json.dumps(config))