import pdfplumber
import re
# the command to clear is `cls` on Windows and `clear` on most everything else
from decimal import Decimal
from datetime import datetime
from models import Transaction
year = 2026


def read_pdf():
    overall_income = 0
    start_pattern = r"(?m)^\d{2}\.\d{2}\.[ \t]+"
    patterns = {
        "date":{
            "pattern": r"Období:\s*(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})\s*-\s*(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})",
            "type": "date_range"
        },
        "currency": {
            "pattern": r"Měna:\s(\w+)",
            "type": "str"
        },
        "initial_balance": {
            "pattern": r"Počáteční zůstatek:\s*([\d ]+,\d{2})",
            "type": "decimal",
        },
        "final_balance": {
            "pattern": r"Konečný zůstatek:\s*([\d ]+,\d{2})",
            "type": "decimal",
        },
        "total_income": {
            "pattern": r"Celkové příjmy:\s*([\d ]+,\d{2})",
            "type": "decimal",
        },
        "total_expenses": {
            "pattern": r"Celkové výdaje:\s*([\d ]+,\d{2})",
            "type": "decimal",
        }
    }
    transaction_patterns = {
        "card_payment": r"(\d{2}\.\d{2})\.\s+Transakce\s+platební\s+kartou\s+\d+\s+(-?\d+(?: \d{3})*,\d{2})\s+(-?\d+(?: \d{3})*,\d{2})\n\d+\s+\d+\s+\d+\nMísto:\s+([\w. ]+)\s+(Praha|Prague)( [\w\- ]+)?\n",
        "top_up": r"(\d{2}\.\d{2})\.\s+Platba\s+služeb\s+mobilního\s+operátora\s+DOBÍJENÍ\s+O2\s+\d+\s+(-?\d+(?: \d{3})*,\d{2})\s+(-?\d+(?: \d{3})*,\d{2})\n",
        # "savings_got": r"(\d{2}\.\d{2})\.\s+Bezhotovostní\s+převod\s+EB\s+[",
            "sent_to_me": r"(\d{2}\.\d{2})\.[ \t]+Příchozí[ \t]+úhrada[ \t]+okamžitá[ \t]+([^\d\n]+?)[ \t]+\d+[ \t]+(-?\d+(?: \d{3})*,\d{2})[ \t]+(-?\d+(?: \d{3})*,\d{2})\n(\d+/\d{4})",
            "sent_from_me": r"(\d{2}\.\d{2})\.[ \t]+Odchozí[ \t]+úhrada[ \t]+okamžitá[ \t]+([^\d\n]+?)[ \t]+\d+[ \t]+(-?\d+(?: \d{3})*,\d{2})[ \t]+(-?\d+(?: \d{3})*,\d{2})\n(\d+/\d{4})",
        }
    transactions_calculated = []
    table_patterns = {

    }
    merchants_old = {
        "action b032": "Action",
        "lidl dekuje za nakup": "Lidl",
        "dm dekuje za vas naku": "dm",
        "albert vam dekuje": "Albert",
        "bageterie boulevard": "Bageterie",
        "alza.cz": "Alza",
        "kaufland cz": "Kaufland",
    }
    merchants = {
        "KFC": ["kfc"],
        "Lidl": ["lidl"],
        "Albert": ["albert"],
        "Billa": ["billa"],
        "Burger King": ["bk palladium", "bk", "bk praha"],
        "McDonalds": ["mcdonalds"],
        "DM": ["dm", "dm dekuje za vas naku"],
        "Kaufland": ["kaufland"],
        "Cafes": ["kavarna"],
        "Reserved": ["reserved"],
        "Bageterie": ["bageterie"],
        "Alza": ["alza.cz"],
        "Kytary": ["kytary.cz"],
        "Action": ["Action"]
    }
    categories = {
        "KFC": "fast_food",
        "Lidl": "groceries",
        "Albert": "groceries",
        "Billa": "groceries",
        "Burger King": "fast_food",
        "McDonalds": "fast_food",
        "DM": "toiletries",
        "Kaufland": "groceries",
        "Cafes": "cafes",
        "Reserved": "clothing",
        "Bageterie": "fast_food",
        "Alza": "tech",
        "Kytary": "music",
        "Action": "general_shopping",
        "Other": "other",
        "outgoing payment": "outgoing payment",
        "incoming payment": "incoming payment"
    }
    results = {}
    with pdfplumber.open("statements/statement26_10.pdf") as pdf:

        page_text = ""
        for p_page in pdf.pages:
            page_text += p_page.extract_text()

        print(repr(page_text))

        for name, pattern_dict in patterns.items():
            value_type, pattern = pattern_dict.get("type", "str"), pattern_dict.get("pattern", "")

            match = re.search(pattern, page_text)
            if match:
                results[name] = parse_main_values(match, value_type)

        statement_year = results.get("date").get("end").year

        header = "Protiúčet nebo poznámka VS KS SS"

        start = page_text.find(header)

        if start == -1:
            raise ValueError("Transaction table not found")

        table_text = page_text[start + len(header):]
        matches = list(re.finditer(start_pattern, table_text))

        transaction_blocks = []

        for i, match in enumerate(matches):
            start = match.start()

            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(table_text)

            block = table_text[start:end].strip()
            transaction_blocks.append(block)

        recognized_transactions = 0
        overall_transactions = len(transaction_blocks)
        for t_block in transaction_blocks:
            for t_type, t_pattern in transaction_patterns.items():
                x_match = re.search(t_pattern, t_block, re.IGNORECASE)

                if not x_match:
                    continue

                recognized_transactions += 1

                t_date = parse_table_values(x_match.group(1), "date", statement_year)
                second_party = None
                if t_type in ["card_payment", "top_up"]:
                    t_amount = parse_table_values(x_match.group(2), "decimal")
                else:
                    second_party = parse_table_values(x_match.group(2), "str")
                    t_amount = parse_table_values(x_match.group(3), "decimal")
                t_recipient = None
                t_sender = None
                t_merchant = None
                merchant_message = None
                if t_type == "card_payment":
                    merchant_message = parse_table_values(x_match.group(4).lower(), "str")
                    t_merchant = identify_merchant(merchant_message, merchants)
                elif t_type == "sent_to_me":
                    t_merchant = None
                    t_category = "incoming payment"
                    t_sender = second_party
                elif t_type == "sent_from_me":
                    t_merchant = None
                    t_category = "outgoing payment"
                    t_recipient = second_party
                else:
                    t_merchant = "Other"

                if t_merchant:
                    t_category = categories.get(t_merchant, "Other")

                transactions_calculated.append(Transaction(
                    date=t_date,
                    amount=t_amount,
                    currency="CZK",
                    type=t_type,
                    merchant=t_merchant,
                    merchant_message=merchant_message,
                    category=t_category,
                    sender=t_sender,
                    recipient=t_recipient
                ))

                break

        for T in transactions_calculated:
            print(T)

        show_statistics(transactions_calculated, categories, results["date"])
        print("=============================================")
        print(f"Overall {overall_transactions}")
        print(f"Overall recognised {recognized_transactions}")
        print("=============================================")
        print(results)


def parse_main_values(match, value_type, statement_year=0):
    if value_type == "str":
        return match.group(1)

    elif value_type == "decimal":
        value = match.group(1)
        value = value.replace(" ", "").replace("\xa0", "")
        value = value.replace(",", ".")
        return Decimal(value)

    elif value_type == "date":
        date = match.replace(" ", "")

        return datetime.strptime(f"{date}.{statement_year}", "%d.%m.%Y").date(),

    elif value_type == "date_range":
        start = match.group(1).replace(" ", "")
        end = match.group(2).replace(" ", "")

        return {
            "start": datetime.strptime(start, "%d.%m.%Y").date(),
            "end": datetime.strptime(end, "%d.%m.%Y").date(),
        }

    raise ValueError(f"Unknown type: {value_type}")


def parse_table_values(string, value_type, statement_year=0):
    if value_type == "str":
        return str(string)

    elif value_type == "decimal":
        value = string.replace(" ", "").replace("\xa0", "")
        value = value.replace(",", ".")
        return Decimal(value)

    elif value_type == "date":
        date = string.replace(" ", "")

        return datetime.strptime(f"{date}.{statement_year}", "%d.%m.%Y").date()

    raise ValueError(f"Unknown type: {value_type}")


def identify_merchant(m_message, merchants):
    message = m_message.casefold()

    for merchant, m_keywords in merchants.items():
        for keyword in m_keywords:
            if keyword.casefold() in message:
                return merchant
    return "Other"


def show_statistics(transactions, categories, period):
    unique_categories = sorted(list(set(categories.values())))
    statistics = {}
    sum = 0
    for category in unique_categories:
        for t_item in transactions:
            if t_item.category == category:
                sum += t_item.amount
        statistics[category] = sum
        print("--------------------------------------------------------------------------")
        print(f"{period.get('start')}-{period.get('end')} in category {category} you had spent {sum} CZK")
        sum = 0
    print("--------------------------------------------------------------------------")

def extract_transactions(pdf):
    pass

def categorize_transaction(transaction):
    pass

def calculate_monthly_expenses(transactions):
    pass


def main():
    # # Your program starts here
    # os.system('cls' if os.name == 'nt' else 'clear')
    read_pdf()
    print("CSOB Expense Tracker")


if __name__ == "__main__":
    main()
