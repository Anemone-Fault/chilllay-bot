from tortoise import fields, models
from enum import Enum

class RequestStatus(str, Enum):
    CREATED = "created"
    PRICE_SET = "price_set"
    COMPLETED = "completed"
    CANCELED = "canceled"

class Rarity(str, Enum):
    COMMON = "Обычный"
    RARE = "Редкий"
    EPIC = "Эпический"
    CHILL = "Чилловый"

class GiftType(str, Enum):
    MONEY = "Чилликовый"
    ITEM = "Предметный"
    TALENT = "Талантливый"
    LUCKY = "Удачливый"
    FATE = "Судьбоносный"

class ItemType(str, Enum):
    ITEM = "Предмет"
    TALENT = "Талант"
    ABILITY = "Способность"

class User(models.Model):
    vk_id = fields.BigIntField(pk=True)
    first_name = fields.CharField(max_length=255)
    last_name = fields.CharField(max_length=255)
    balance = fields.IntField(default=100) 
    karma = fields.IntField(default=0)
    
    card_photo_id = fields.CharField(max_length=100, null=True)
    card_comment_id = fields.IntField(null=True)
    
    is_admin = fields.BooleanField(default=False)
    is_banned = fields.BooleanField(default=False)
    last_bonus = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    # Зарплата
    rp_pending_balance = fields.IntField(default=0)
    rp_monthly_chars = fields.IntField(default=0)

    class Meta:
        table = "users"
    
    def get_rank(self) -> str:
        suffix = " (Гниль 💩)" if self.karma < -10 else ""
        b = self.balance
        if b < 1000: return f"Амеба 🦠{suffix}"
        if b < 5000: return f"Биомусор 🗑{suffix}"
        if b < 20000: return f"Попущ 🤡{suffix}"
        if b < 50000: return f"Говночист 🚽{suffix}"
        if b < 100000: return f"Крыса 🐀{suffix}"
        if b < 500000: return f"Скам-мамонт 🐒{suffix}"
        if b < 1000000: return f"Шизоид при бабках 💊{suffix}"
        return f"Папик 👑{suffix}"

class SystemConfig(models.Model):
    key = fields.CharField(pk=True, max_length=50)
    value = fields.CharField(max_length=255)

class Item(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    description = fields.TextField(default="Описание от администрации")
    rarity = fields.CharEnumField(Rarity, default=Rarity.COMMON)
    type = fields.CharEnumField(ItemType, default=ItemType.ITEM)
    photo_id = fields.CharField(max_length=100, null=True)
    class Meta: table = "items"

class Inventory(models.Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="inventory")
    item = fields.ForeignKeyField("models.Item", related_name="owners")
    quantity = fields.IntField(default=1)
    class Meta: table = "inventory"; unique_together = ("user", "item")

class GiftBox(models.Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="gifts")
    rarity = fields.CharEnumField(Rarity, default=Rarity.COMMON)
    gift_type = fields.CharEnumField(GiftType, default=GiftType.MONEY)
    quantity = fields.IntField(default=0)
    class Meta: table = "gift_boxes"

class ShopRequest(models.Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="requests")
    item_text = fields.TextField()
    price = fields.IntField(null=True)
    status = fields.CharEnumField(RequestStatus, default=RequestStatus.CREATED)
    created_at = fields.DatetimeField(auto_now_add=True)

class TransactionLog(models.Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="transactions")
    amount = fields.IntField()
    description = fields.CharField(max_length=255)
    created_at = fields.DatetimeField(auto_now_add=True)

class Cheque(models.Model):
    code = fields.CharField(pk=True, max_length=10)
    creator_id = fields.BigIntField()
    total_amount = fields.IntField()
    amount_left = fields.IntField()
    activations_limit = fields.IntField(default=1)
    activations_current = fields.IntField(default=0)
    mode = fields.CharField(max_length=10, default="fix")
    users_activated = fields.JSONField(default=list)
    created_at = fields.DatetimeField(auto_now_add=True)

class Promo(models.Model):
    code = fields.CharField(pk=True, max_length=50)
    amount = fields.IntField()
    max_activations = fields.IntField()
    current_activations = fields.IntField(default=0)
    users_activated = fields.JSONField(default=list)

