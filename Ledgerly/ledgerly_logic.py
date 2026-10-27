from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def format_money(value, currency="PKR"):
    try:
        amount = Decimal(str(value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        amount = Decimal("0.00")
    return f"{currency} {amount:,.2f}" if amount % 1 else f"{currency} {amount:,.0f}"


def parse_decimal(value, label, minimum=Decimal("0"), maximum=Decimal("999999999")):
    try:
        result = Decimal(str(value or "0").strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f"{label} must be a valid number.")
    if not result.is_finite() or result < minimum or result > maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}.")
    return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_date(value, label):
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        raise ValueError(f"Please enter a valid {label.lower()}.")


def invoice_total(subtotal, tax_rate, discount):
    tax = (subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = max(Decimal("0.00"), subtotal + tax - discount)
    return tax, total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
