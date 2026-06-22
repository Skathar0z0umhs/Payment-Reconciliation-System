"""
store.py — the application's MEMORY, using SQLAlchemy 2.0 (ORM, typed style).

Persists information BETWEEN runs in a single SQLite file:
  * outstanding_orders : orders still unpaid, carried over to future runs
  * run_history        : one row per reconciliation run (history log)

The public interface is DataFrame-in / DataFrame-out, so it plugs straight
into the pandas-based pipeline.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, String, Integer, Float, DateTime, select, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

logger = logging.getLogger(__name__)


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get(
    "DATA_DIR",
    os.path.join(_PROJECT_ROOT, "data"),
)
os.makedirs(DATA_DIR, exist_ok=True)          # create the folder if missing
DB_PATH = os.path.join(DATA_DIR, "reconciliation.db")

# The Engine is the single entry point to the database (manages connections).
# Create it ONCE and reuse it everywhere.  "sqlite:///<path>" is the SQLAlchemy URL.
ENGINE = create_engine(f"sqlite:///{DB_PATH}", echo=False)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)



class Base(DeclarativeBase):
    pass


class OutstandingOrder(Base):
    __tablename__ = "outstanding_orders"

    id:             Mapped[int]              = mapped_column(Integer, primary_key=True)
    receipt_number: Mapped[int | None]       = mapped_column(Integer, nullable=True)
    order_id:       Mapped[int | None]       = mapped_column(Integer, nullable=True)
    name:           Mapped[str | None]       = mapped_column(String,  nullable=True)
    amount_paid:    Mapped[float | None]     = mapped_column(Float,   nullable=True)
    date:           Mapped[str | None]       = mapped_column(String,  nullable=True)
    first_seen:     Mapped[datetime]         = mapped_column(DateTime, default=_utcnow)


class RunHistory(Base):
    __tablename__ = "run_history"

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True)
    run_time:   Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    matched:    Mapped[int]      = mapped_column(Integer)
    unpaid:     Mapped[int]      = mapped_column(Integer)
    newly_paid: Mapped[int]      = mapped_column(Integer)


# Helpers
def _clean(value):
    """Convert pandas/numpy scalars (NaN, pd.NA, numpy.int64...) into plain
    Python values that SQLAlchemy can store."""
    if value is pd.NA or (pd.api.types.is_scalar(value) and pd.isna(value)):
        return None
    return value.item() if hasattr(value, "item") else value


#  Public API 
def init_db() -> None:
    Base.metadata.create_all(ENGINE)
    logger.info("Database ready at %s", DB_PATH)


def save_outstanding_orders(df: pd.DataFrame) -> None:
    keep = ["receipt_number", "order_id", "name", "amount_paid", "date"]
    cols = [c for c in keep if c in df.columns]
    records = df[cols].copy()
    # SQLite can't bind a pandas Timestamp — store the date as text.
    if "date" in records.columns:
        records["date"] = records["date"].astype(str)
    records = records.to_dict(orient="records")

    # A Session is the unit of work: open it, do changes, commit.
    with Session(ENGINE) as session:
        session.execute(delete(OutstandingOrder))               # clear old ledger
        session.add_all([
            OutstandingOrder(**{k: _clean(row[k]) for k in cols})
            for row in records
        ])
        session.commit()
    logger.info("Saved %d outstanding orders to the ledger.", len(records))


def load_outstanding_orders() -> pd.DataFrame:
    """Read the outstanding-orders ledger back into a DataFrame."""
    with Session(ENGINE) as session:
        rows = session.scalars(select(OutstandingOrder)).all()

    df = pd.DataFrame([{
        "receipt_number": r.receipt_number,
        "order_id":       r.order_id,
        "name":           r.name,
        "amount_paid":    r.amount_paid,
        "date":           r.date,
        "first_seen":     r.first_seen,
    } for r in rows])
    logger.info("Loaded %d outstanding orders from the ledger.", len(df))
    return df


def log_run(matched: int, unpaid: int, newly_paid: int) -> None:
    """Append one row to the run history."""
    with Session(ENGINE) as session:
        session.add(RunHistory(matched=matched, unpaid=unpaid, newly_paid=newly_paid))
        session.commit()
    logger.info("Logged run: matched=%d unpaid=%d newly_paid=%d",
                matched, unpaid, newly_paid)
