import pandas as pd 


def export_excel(obj, config: dict):

    with pd.ExcelWriter(config["path"], engine="openpyxl",date_format="YYYY-MM-DD") as writer:

        for sheet_name, attr_name in config["sheets"].items():

            df = getattr(obj, attr_name)

            df.to_excel(
                writer,
                sheet_name=sheet_name[:31],
                index=False
            )