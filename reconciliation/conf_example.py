# ── Example configuration
# A WORKING example, wired to the sample_data/ files, so anyone can run the
# pipeline programmatically out of the box:


CONFIG = {
    'words_to_filter': ["STRIPE", "Paypal", "AMAZON", "Google", "STEUERVERWALTUNG"],
    'bank_sources': [
        {"name": "KSK",                                   # any label you like
         "path": "sample_data/sample_bank_ksk.csv",       # path to the bank CSV
         "sep": ";",                                      # column separator
         "encoding": "cp1252",                            # file encoding
         "columns": ["Verwendungszweck",                  # columns to read
                     "Beguenstigter/Zahlungspflichtiger",
                     "Betrag", "Buchungstag", "Valutadatum"],
         "mapping": {                                     # original -> standard names
             "Verwendungszweck": "transaction_description",
             "Beguenstigter/Zahlungspflichtiger": "client_name",
             "Betrag": "amount",
             "Buchungstag": "booking_date",
             "Valutadatum": "transaction_date",
         },
         "parse_dates": ["Buchungstag", "Valutadatum"],   # date columns
         "format": "%Y-%m-%d"
        },
        {"name": "Grenke",
         "path": "sample_data/sample_bank_grenke.csv",
         "sep": ";",
         "encoding": "cp1252",
         "columns": ["Verwendungszweck",
                     "Name Zahlungsbeteiligter",
                     "Betrag", "Buchungstag", "Valutadatum"],
         "mapping": {
            "Verwendungszweck": "transaction_description",
            "Name Zahlungsbeteiligter": "client_name",
            "Betrag": "amount",
            "Buchungstag": "booking_date",
            "Valutadatum": "transaction_date",
         },
         "parse_dates": ["Buchungstag", "Valutadatum"],
         "format": "%Y-%m-%d"
        }
        # Add more bank sources as dictionaries, separated by commas.
    ],
    "orders_sources": {
        "name": "orders",
        "path": "sample_data/sample_orders.csv",
        "columns": ["Date", "Re Nummer", "Order ID", "Name", "Summe", "Zahlungsart"],
        "mapping": {
            "Date": "date",
            "Re Nummer": "receipt_number",
            "Order ID": "order_id",
            "Name": "name",
            "Summe": "amount_paid",
            "Zahlungsart": "payment_method",
        },
        "parse_dates": ["Date"],
        "format": "%Y-%m-%d",
        "payment_method_to_filter": "bacs",   # only reconcile this payment method
    }
}

# Matching tolerances and ID-detection thresholds (tune without touching processor.py).
MATCH_CONFIG = {
    "amount_tolerance": 3.00,    # max € difference for an "amount match"
    "date_window_days": 15,      # max days between order date and bank date
    "receipt_number_max": 12000, # a 5-digit number BELOW this is a receipt number
    "order_id_min": 20000,       # a 5-digit number ABOVE this is an order id
}

EXPORT_CONFIG = {
    "type": "excel",
    "path": "reconciliation_report.xlsx",   # output file name
    "sheets": {
        "Unpaid Orders": "unmatched_orders",
        "Matched Orders": "matched_rows",
        "Unmatched_Payments": "unmatched_payments",
    },
}
