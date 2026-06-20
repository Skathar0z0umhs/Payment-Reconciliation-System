import pandas as pd
from .schema import STANDARD_BANK_COLUMNS, STANDARD_ORDER_COLUMNS


def load_orders(orders_source : dict) -> pd.DataFrame:
    df = pd.read_csv(orders_source.get('path'), 
                     usecols=orders_source.get('columns'), 
                     parse_dates=orders_source.get('parse_dates', None)
                     
                     )

    df = df.rename(columns=orders_source.get('mapping'))

    # validation
    missing = set(STANDARD_ORDER_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")


    return df
def load_bank(bank_source : dict) -> pd.DataFrame:
    df = pd.read_csv(bank_source.get('path'), 
                     sep=bank_source.get('sep'), 
                     encoding=bank_source.get('encoding'), 
                     usecols=bank_source.get('columns'),
                     parse_dates=bank_source.get('parse_dates', None),
                     

                     )

    df = df.rename(columns=bank_source.get('mapping'))

    # validation
    missing = set(STANDARD_BANK_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")


    return df
   


