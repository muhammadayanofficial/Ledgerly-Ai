import unittest
from decimal import Decimal

from ledgerly_logic import invoice_total, parse_decimal, parse_date, format_money


class LedgerlyCalculationTests(unittest.TestCase):
    def test_tax_and_discount_calculation(self):
        tax, total = invoice_total(Decimal("1000.00"), Decimal("10.00"), Decimal("50.00"))
        self.assertEqual(tax, Decimal("100.00"))
        self.assertEqual(total, Decimal("1050.00"))

    def test_total_never_goes_below_zero(self):
        tax, total = invoice_total(Decimal("50.00"), Decimal("0"), Decimal("70.00"))
        self.assertEqual(tax, Decimal("0.00"))
        self.assertEqual(total, Decimal("0.00"))

    def test_decimal_rounds_to_cents(self):
        self.assertEqual(parse_decimal("12.345", "Price"), Decimal("12.35"))

    def test_rejects_negative_price(self):
        with self.assertRaises(ValueError):
            parse_decimal("-1", "Price")

    def test_rejects_tax_above_one_hundred_percent(self):
        with self.assertRaises(ValueError):
            parse_decimal("101", "Tax rate", Decimal("0"), Decimal("100"))

    def test_money_formatting(self):
        self.assertEqual(format_money("12000.00", "PKR"), "PKR 12,000")
        self.assertEqual(format_money("12000.50", "USD"), "USD 12,000.50")

    def test_date_validation(self):
        self.assertEqual(parse_date("2026-10-27", "Issue date"), "2026-10-27")
        with self.assertRaises(ValueError):
            parse_date("not-a-date", "Issue date")


if __name__ == "__main__":
    unittest.main()
