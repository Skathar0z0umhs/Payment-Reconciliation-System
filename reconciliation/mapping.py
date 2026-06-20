ORDERS_MAPPING  = {
    "Date": "date",
    "Re Nummer": "receipt_number",
    "Order ID": "order_id",
    "Name": "name",
    "Summe": "amount_paid",
    "Zahlungsart": "payment_method",
}
BANK_KREIS_MAPPING = {
    "Verwendungszweck": "transaction_description",
    "Beguenstigter/Zahlungspflichtiger": "client_name",
    "Betrag": "amount",
    "Buchungstag": "booking_date",
    "Valutadatum": "transaction_date",
}
BANK_GRENKE_MAPPING = {
    "Verwendungszweck": "transaction_description",
    "Name Zahlungsbeteiligter": "client_name",
    "Betrag": "amount",
    "Buchungstag": "booking_date",
    "Valutadatum": "transaction_date",
}