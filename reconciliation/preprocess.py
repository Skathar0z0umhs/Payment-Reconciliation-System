import pandas as pd


def clean_orders(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset= ["name"])
    df = df.drop_duplicates(subset="receipt_number")
    # Receipt comes as "RE-11469" -> keep the number after the dash.
    df["receipt_number"] = df["receipt_number"].str.split("-").str[1]
    df["receipt_number"] = df["receipt_number"].astype("Int64")
    df["order_id"] = pd.to_numeric(df["order_id"], errors='coerce')
    df["name"] = df["name"].astype("string").str.strip().str.lower()
    # European decimals use a comma ("100,50") -> convert to a float.
    df["amount_paid"] = df["amount_paid"].astype("string").str.replace(",", ".")
    df["amount_paid"] = df["amount_paid"].astype(float)
    df["payment_method"] = df["payment_method"].astype("string").str.strip().str.lower()
    return df


def clean_bank(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(how = 'all')
    df = df.drop_duplicates()
    df["transaction_description"] = df["transaction_description"].astype("string").str.strip().str.lower()
    df["client_name"] = df["client_name"].astype("string").str.strip().str.lower()
    df["amount"] = df["amount"].astype("string").str.replace(",", ".")
    df["amount"] = df["amount"].astype(float)
    # Keep only incoming payments (positive amounts); drop outgoing ones.
    df= df[df["amount"] > 0]
    return df



