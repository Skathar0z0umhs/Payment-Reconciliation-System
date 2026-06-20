import pandas as pd
from . import loader
from . import preprocess
from . import processor
from . import exporter
from . import store
from .conf_example import EXPORT_CONFIG, MATCH_CONFIG
import logging

# A logger named "pipeline" (because __name__ == "pipeline" in this file).
# Every message it emits will show that name, so you know where it came from.
logger = logging.getLogger(__name__)


class ReconcilliationPipeline:
    def __init__(self,config : dict):
      
      # Input State
      self.config = config
      

      # Internal State
      self.orders = None
      self.bank = None
      self.orders_work = None
      self.bank_work = None


      # Output State
      self.matched_rows = None
      self.matched_payments = None
      self.unmatched_orders = None
      self.unmatched_payments = None

      # Memory State (carried over between runs)
      self.carryover_receipts = set()   # receipt numbers loaded from the ledger
      self.newly_paid = None            # orders that JUST got paid in this run

      
   
    def load(self):
        try:
            self.orders = loader.load_orders(self.config['orders_sources'])
        except Exception as e:
            raise ValueError(f"Orders load failed: {e}")
        try:
            self.bank = pd.concat(
            [loader.load_bank(source) for source in self.config['bank_sources']],
            ignore_index=True
        )
        except Exception as e:
            raise ValueError(f"Bank load failed: {e}")
        logger.info("Loaded %d orders and %d bank rows.", len(self.orders), len(self.bank))

    def copy(self):
        self.orders_work = processor.copy(self.orders)
        self.bank_work = processor.copy(self.bank)
        logger.info("Data copied for processing.")
        

    def clean(self):
        self.orders_work = preprocess.clean_orders(self.orders_work)
        self.bank_work = preprocess.clean_bank(self.bank_work)
        logger.info("Cleaned: %d orders, %d bank rows remain.",
                    len(self.orders_work), len(self.bank_work))

    def preprocess_data(self):
        match_cfg = self.config.get("match", MATCH_CONFIG)
        self.bank_work = processor.extract_re_nummer_or_order_id_from_transaction_description(self.bank_work)
        self.bank_work = processor.extract_receipt_and_order_id_from_five_digits(
            self.bank_work,
            receipt_number_max=match_cfg["receipt_number_max"],
            order_id_min=match_cfg["order_id_min"],
        )
        self.orders_work = processor.filter_payment_method(self.orders_work, self.config["orders_sources"]['payment_method_to_filter'])
        self.bank_work = processor.transform_receipt_number_and_order_id_to_int(self.bank_work)
        self.orders_work = processor.tokenize_name(self.orders_work, "name")
        self.bank_work = processor.tokenize_name(self.bank_work, "client_name")
        self.bank_work = processor.filter_unnecessary_data_by_word(self.bank_work, self.config['words_to_filter'])
        logger.info("Preprocessed: %d orders (payment_method='%s'), %d bank rows after word filter.",
                    len(self.orders_work),
                    self.config["orders_sources"]['payment_method_to_filter'],
                    len(self.bank_work))

    def load_carryover(self):
        # Pull previously-unpaid orders from the ledger and add them to the
        # current order pool, so new bank payments can match them too.
        outstanding = store.load_outstanding_orders()
        if outstanding.empty:
            return

        outstanding = outstanding.copy()
        # Remember which receipt numbers came from the ledger, so later we can
        # work out which of them just got paid.
        self.carryover_receipts = set(
            pd.to_numeric(outstanding["receipt_number"], errors="coerce").dropna().astype(int)
        )
        # Re-shape the loaded rows into the same match-ready form as orders_work.
        outstanding["receipt_number"] = pd.to_numeric(outstanding["receipt_number"], errors="coerce").astype("Int64")
        outstanding["order_id"]       = pd.to_numeric(outstanding["order_id"], errors="coerce").astype("Int64")
        outstanding["amount_paid"]    = pd.to_numeric(outstanding["amount_paid"], errors="coerce")
        outstanding["date"]           = pd.to_datetime(outstanding["date"], errors="coerce")  # string -> datetime
        outstanding["tokenized_name"] = outstanding["name"].apply(processor.tokenize)
        outstanding = outstanding.drop(columns=["first_seen"], errors="ignore")

        # Add carried-over orders to the working set.
        combined = pd.concat([self.orders_work, outstanding], ignore_index=True)

        # De-duplicate by receipt_number (keep the current-file version), but
        # NEVER collapse rows that have no receipt number (NaN), since several
        # distinct orders could all be missing it.
        has_receipt = combined["receipt_number"].notna()
        combined = pd.concat([
            combined[has_receipt].drop_duplicates(subset="receipt_number", keep="first"),
            combined[~has_receipt],
        ], ignore_index=True)

        self.orders_work = combined
        logger.info("Loaded %d carried-over unpaid orders from the ledger.", len(outstanding))

    def match_by_re_nummer_and_order_id(self):
        self.orders_work, self.bank_work,self.matched_rows = processor.match_receipt_number_and_order_id(self.orders_work, self.bank_work)
        logger.info("ID matching: %d matched, %d orders / %d payments left.",
                    len(self.matched_rows), len(self.orders_work), len(self.bank_work))


    def match_by_name_and_amount(self):
        match_cfg = self.config.get("match", MATCH_CONFIG)
        self.unmatched_orders, self.unmatched_payments,matched_rows_by_name_and_amount = processor.match_by_name_and_amount(
            self.orders_work, self.bank_work,
            amount_tolerance=match_cfg["amount_tolerance"],
            date_window_days=match_cfg["date_window_days"],
        )
        self.matched_rows = pd.concat([self.matched_rows, matched_rows_by_name_and_amount], ignore_index=True)
        logger.info("Name+Amount+Date matching: %d new matches. "
                    "Totals -> matched=%d, unpaid orders=%d, unmatched payments=%d.",
                    len(matched_rows_by_name_and_amount), len(self.matched_rows),
                    len(self.unmatched_orders), len(self.unmatched_payments))


    def return_original_data(self):
        self.unmatched_orders = processor.return_original_data(self.unmatched_orders)
        self.matched_rows = processor.return_original_data(self.matched_rows)
        self.unmatched_payments = processor.return_original_data(self.unmatched_payments)
        logger.info("Original data restored for output.")


    def export(self):
        exporter.export_excel(self, EXPORT_CONFIG)
        logger.info("Data exported successfully.")


    def detect_newly_paid(self):
        # Before/after comparison: which carried-over orders just got paid.
        # Called BEFORE return_original_data(), while columns are still lowercase.
        if self.unmatched_orders is not None and not self.unmatched_orders.empty:
            still_unpaid = set(
                pd.to_numeric(self.unmatched_orders["receipt_number"], errors="coerce")
                .dropna().astype(int)
            )
        else:
            still_unpaid = set()

        # Just paid = was in the ledger BUT is no longer unpaid.
        newly_paid_receipts = self.carryover_receipts - still_unpaid

        # Pull the matching rows from matched_rows (they have a "Re Nummer" column).
        if newly_paid_receipts and self.matched_rows is not None and "Re Nummer" in self.matched_rows.columns:
            mask = pd.to_numeric(self.matched_rows["Re Nummer"], errors="coerce").isin(newly_paid_receipts)
            self.newly_paid = self.matched_rows[mask].copy()
        else:
            self.newly_paid = None

        logger.info("Newly paid since last run: %d orders.", len(newly_paid_receipts))

    def save_to_db(self):
        # Persist the still-unpaid orders to the ledger.
        # Called BEFORE return_original_data(), so columns are still lowercase
        # (receipt_number, order_id, name, amount_paid, date) — exactly what
        # store.save_outstanding_orders() expects.
        store.save_outstanding_orders(self.unmatched_orders)
        logger.info("Saved unpaid orders to the database.")

    
    
    

    def run(self):
        store.init_db()          # make sure the DB tables exist
        self.load()
        self.copy()
        self.clean()
        self.preprocess_data()
        self.load_carryover()          # add remembered unpaid orders before matching
        self.match_by_re_nummer_and_order_id()
        self.match_by_name_and_amount()
        self.detect_newly_paid()          # which carried-over orders just got paid
        self.save_to_db()                 # save unpaid orders (lowercase columns)
        self.return_original_data()
        #self.export()   # edit EXPORT_CONFIG in conf_example.py to enable export
        logger.info("Pipeline executed successfully!")
        
        

        
        
        
        
        
    
    

    


    
        
       
        
    
   