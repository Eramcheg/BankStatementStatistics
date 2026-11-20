from dataclasses import dataclass
from datetime import date
from decimal import Decimal

@dataclass
class Transaction:
    date: date
    amount: Decimal
    currency: str
    type: str
    merchant: str | None
    merchant_message: str | None
    recipient: str | None
    sender: str | None
    category: str = "unknown"

    def __init__(self, date, amount, currency, type, merchant, merchant_message, category, recipient=None, sender=None):
        self.date = date
        self.amount = amount
        self.currency = currency
        self.type = type
        self.merchant = merchant
        self.merchant_message = merchant_message
        self.category = category
        self.sender = sender
        self.recipient = recipient

    def __str__(self):
        return f"{self.type} from {self.date} in {self.merchant}: {self.amount} {self.currency}"