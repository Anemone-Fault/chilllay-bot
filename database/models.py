from tortoise import fields, models
from enum import Enum

class RequestStatus(str, Enum):
    CREATED = "created"
    PRICE_SET = "price_set"
    COMPLETED = "completed"
    CANCELED = "canceled"

class User(models.Model):
    vk_id = fields.BigIntField(pk=True)
    first_name = fields.CharField(max_length=255)
    last_name = fields.CharField(max_length=255)
    balance = fields.IntField(default=1000)
    karma = fields.IntField(default=0)
    is_admin = fields.BooleanField(default=False)
    is_banned = fields.BooleanField(default=False)
    last_bonus = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"
    
    def get_rank(self) -> str:
        suffix = " (Гниль 💩)" if self.karma < -10 else ""
        b = self.balance
        if b < 1000: return f"Биомусор 🦠{suffix}"
        if b < 5000: return f"Попущ 🤡{suffix}"
        if b < 20000: return f"Говночист 🚽{suffix}"
        if b < 50000: return f"Крыса канцелярская 🐀{suffix}"
        if b < 100000: return f"Скам-мамонт 🐒{suffix}"
        if b < 500000: return f"Душнила 👺{suffix}"
        if b < 1000000: return f"Шизоид при бабках 💊{suffix}"
        return f"Папик 👑{suffix}"

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
    amount_left = fields.IntField() # Исправление: точный учет остатка
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