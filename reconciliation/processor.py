import pandas as pd 
import unicodedata
import re 


def copy(df: pd.DataFrame) -> pd.DataFrame:
    new_df = df.copy().reset_index(drop=True)
    return new_df


def extract_re_nummer_or_order_id_from_transaction_description(bank_df: pd.DataFrame) -> pd.DataFrame:
    # Find every standalone 5-digit number in the transaction text. The
    # (?<!\d) / (?!\d) guards make sure we don't grab 5 digits out of a longer number.
    bank_df["five_digits"] = bank_df["transaction_description"].fillna("").str.findall(r"(?<!\d)\d{5}(?!\d)")
    bank_df["five_digits"] = bank_df["five_digits"].apply(lambda x: [int(i) for i in x])
    return bank_df


def extract_receipt_and_order_id_from_five_digits(bank_df: pd.DataFrame,
                                                   receipt_number_max: int = 12000,
                                                   order_id_min: int = 20000) -> pd.DataFrame:
    bank_df["receipt_number"] = bank_df["five_digits"].apply(
        lambda x: next((i for i in x if i < receipt_number_max), None)
    )
    bank_df["order_id"] = bank_df["five_digits"].apply(
        lambda x: next((i for i in x if i > order_id_min), None)
    )
    return bank_df


def filter_payment_method(orders_df: pd.DataFrame, method_pay: str) -> pd.DataFrame:
    orders_df  = orders_df[orders_df['payment_method'] == method_pay]
    return orders_df


def transform_receipt_number_and_order_id_to_int(bank_df: pd.DataFrame) -> pd.DataFrame:
    bank_df["receipt_number"] = pd.to_numeric(bank_df["receipt_number"].astype("Int64"), errors='coerce')
    bank_df["order_id"] = pd.to_numeric(bank_df["order_id"].astype("Int64"), errors='coerce')
    return bank_df


def concatanate_banks(bank1: pd.DataFrame, bank2: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([bank1, bank2], ignore_index=True)


def tokenize(x):
    if pd.isna(x):
        return []

    # Strip German accents/umlauts (e.g. "ü" -> "u") so names compare reliably.
    # NFKD splits each accented letter into base letter + accent mark, then we
    # drop the accent marks.
    x = unicodedata.normalize("NFKD", str(x))
    x = "".join(c for c in x if not unicodedata.combining(c))

    x = x.lower()

    # Keep only letter-words (drop digits, punctuation, underscores).
    return re.findall(r"[^\W\d_]+", x)


def tokenize_name(df: pd.DataFrame, column : str) -> pd.DataFrame:
    df['tokenized_name'] = df[column].apply(tokenize)
    return df


def match_receipt_number_and_order_id(orders_work: pd.DataFrame, bank_work: pd.DataFrame) -> pd.DataFrame:
    # Pass 1 (exact): for each order, find a bank payment with the same receipt
    # number, otherwise the same order id. A match removes the row from both sides.
    # reset_index keeps positional .iloc and label-based .drop aligned.
    orders_work = orders_work.reset_index(drop=True)
    bank_work = bank_work.reset_index(drop=True)
    matched_rows = []
    i = 0
    while i < len(orders_work):
        order = orders_work.iloc[i]
        match_type = None
        match = bank_work[bank_work["receipt_number"] == order["receipt_number"]]


        if len(match) > 0:
            match_type = "Receipt Number"
       
        if len(match) == 0:
            match = bank_work[bank_work["order_id"] == order["order_id"]]
            match_type = "Order ID"
       
        if len(match) > 0:
            payment_idx = match.index[0]
            matched_payment = match.iloc[0]

            matched_rows.append(
                {
                    "Order Name": order["name"],
                    "Order Amount": order["amount_paid"],
                    "Bank Amount": matched_payment["amount"],
                    "Order Date": order["date"],
                    "Bank Date": matched_payment["transaction_date"],
                    "Re Nummer": order["receipt_number"],
                    "Order ID": order["order_id"],
                    "Bank Re Nummer": matched_payment["receipt_number"],
                    "Bank Order ID ": matched_payment["order_id"],
                    "Match Type" : match_type
                }
            )
            orders_work = orders_work.drop(orders_work.index[i]).reset_index(drop=True)

            bank_work = bank_work.drop(payment_idx).reset_index(drop=True)
            # Do NOT advance i: after dropping + reindexing, the next order has
            # shifted into position i.

        else:
            i += 1

    return  orders_work, bank_work,pd.DataFrame(matched_rows)


def match_by_name_and_amount(orders_work: pd.DataFrame, bank_work: pd.DataFrame,
                             amount_tolerance: float = 3.00,
                             date_window_days: int = 15) -> pd.DataFrame:
    orders_work = orders_work.reset_index(drop=True)
    bank_work = bank_work.reset_index(drop=True)
    orders_work["date"] = pd.to_datetime(orders_work["date"], errors="coerce", dayfirst=True)
    bank_work["transaction_date"] = pd.to_datetime(bank_work["transaction_date"], errors="coerce", dayfirst=True)
    i = 0
    matched_rows = []
    while i < len(orders_work):
        order = orders_work.iloc[i]
        order_tokens = set(order["tokenized_name"])
        best_match_pos = None
        best_score = 0

        # Pass 2 (fuzzy): a payment qualifies ONLY if amount AND date AND name
        # all agree. Among the qualifying payments, keep the strongest name overlap.
        for pos in range(len(bank_work)):
            payment = bank_work.iloc[pos]

            # 1) amount must match within tolerance
            if pd.isna(order["amount_paid"]) or pd.isna(payment["amount"]):
                continue
            if abs(order["amount_paid"] - payment["amount"]) >= amount_tolerance:
                continue

            # 2) date must be within the window
            if pd.isna(order["date"]) or pd.isna(payment["transaction_date"]):
                continue
            if abs((order["date"] - payment["transaction_date"]).days) > date_window_days:
                continue

            # 3) names must share at least one token
            name_score = len(order_tokens.intersection(set(payment["tokenized_name"])))
            if name_score < 1:
                continue

            if name_score > best_score:
                best_score = name_score
                best_match_pos = pos

        if best_match_pos is not None:
            # Capture the matched payment BEFORE dropping it
            matched_payment = bank_work.iloc[best_match_pos]
            matched_rows.append({
                    "Order Name": order["name"],
                    "Order Amount": order["amount_paid"],
                    "Bank Amount": matched_payment["amount"],
                    "Order Date": order["date"],
                    "Bank Date": matched_payment["transaction_date"],
                    "Re Nummer": order["receipt_number"],
                    "Order ID": order["order_id"],
                    "Bank Re Nummer": matched_payment["receipt_number"],
                    "Bank Order ID ": matched_payment["order_id"],
                    "Match Type" : "Name+Amount+Date"
                    })
            orders_work = orders_work.drop(orders_work.index[i]).reset_index(drop=True)
            bank_work = bank_work.drop(bank_work.index[best_match_pos]).reset_index(drop=True)

        else:
            i += 1

    return orders_work, bank_work,pd.DataFrame(matched_rows)


def filter_unnecessary_data_by_word(bank_df : pd.DataFrame, word: list[str]) -> pd.DataFrame:
    bank_df = bank_df[~bank_df['transaction_description'].str.contains('|'.join(word), case=False, na=False) & ~bank_df['client_name'].str.contains('|'.join(word), case=False, na=False)]
    return bank_df


def return_original_data(orders_df: pd.DataFrame) -> pd.DataFrame:
    if "tokenized_name" in orders_df.columns:
        orders_df.drop("tokenized_name", axis=1, inplace=True)
    if "five_digits" in orders_df.columns:
        orders_df.drop("five_digits", axis=1, inplace=True)
    orders_df.columns = orders_df.columns.str.replace("_", " ").str.title()
    for column in orders_df.columns:
        if orders_df[column].dtype == "string" or orders_df[column].dtype == "object":
            orders_df[column] = orders_df[column].astype(str).str.title()
    return orders_df









