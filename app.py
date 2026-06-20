import streamlit as st
import pandas as pd
import tempfile
import os
import traceback
from io import BytesIO
from reconciliation.logging_config import setup_logging
from reconciliation import store

# Turn on logging for the whole app (screen + reconciliation.log file).
# Without this, every logger.info(...) in the project stays silent.
setup_logging()

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Payment Reconciliation",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ──────────────────────────────────────────────────────────────────
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
    /* ---- Global typography ---- */
    html, body, [class*="css"], .stMarkdown, .stButton, .stDownloadButton {
        font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif;
    }
    /* Trim Streamlit's default top padding for a tighter, app-like feel */
    .block-container { padding-top: 2.2rem; max-width: 1200px; }

    /* ---- Hero header ---- */
    .app-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%);
        padding: 1.8rem 2.2rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 1.8rem;
        box-shadow: 0 10px 30px -12px rgba(30, 58, 95, 0.55);
    }
    .app-header h1 {
        margin: 0; font-size: 2rem; font-weight: 700; letter-spacing: -0.02em;
        display: flex; align-items: center; gap: 0.6rem;
    }
    .app-header p { margin: 0.4rem 0 0; opacity: 0.85; font-size: 0.97rem; font-weight: 400; }

    /* ---- Section / step headers ---- */
    .step-header {
        position: relative;
        padding: 0.55rem 1rem 0.55rem 1.1rem;
        margin: 2rem 0 1rem;
        font-weight: 600;
        font-size: 1.12rem;
        color: #1e3a5f;
        border-left: 4px solid #2d6a9f;
        background: linear-gradient(90deg, #eef4fa 0%, rgba(238,244,250,0) 100%);
        border-radius: 0 8px 8px 0;
    }

    /* ---- Metric cards ---- */
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e6ebf2;
        border-radius: 14px;
        padding: 1.1rem 1.2rem;
        box-shadow: 0 4px 14px -10px rgba(30, 58, 95, 0.35);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 22px -12px rgba(30, 58, 95, 0.45);
    }
    [data-testid="stMetricValue"] { color: #1e3a5f; font-weight: 700; }

    /* ---- Primary (Run) button ---- */
    div[data-testid="stButton"] button[kind="primary"] {
        background: linear-gradient(135deg, #2d6a9f 0%, #1e3a5f 100%);
        border: none; border-radius: 10px; font-weight: 600;
        padding: 0.6rem 1rem;
        box-shadow: 0 6px 18px -8px rgba(45, 106, 159, 0.7);
        transition: filter 0.15s ease, transform 0.15s ease;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        filter: brightness(1.08); transform: translateY(-1px);
    }

    /* ---- Download button ---- */
    div[data-testid="stDownloadButton"] button {
        background: #1f9d57; color: white; font-weight: 600;
        border-radius: 10px; border: none; padding: 0.6rem 1rem;
        box-shadow: 0 6px 18px -8px rgba(31, 157, 87, 0.7);
        transition: filter 0.15s ease, transform 0.15s ease;
    }
    div[data-testid="stDownloadButton"] button:hover {
        filter: brightness(1.08); transform: translateY(-1px);
    }

    /* ---- Tabs ---- */
    .stTabs [data-baseweb="tab-list"] { gap: 0.4rem; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0; padding: 0.4rem 1rem; font-weight: 500;
    }
    .stTabs [aria-selected="true"] { background: #eef4fa; color: #1e3a5f; }

    /* ---- Expanders ---- */
    [data-testid="stExpander"] {
        border: 1px solid #e6ebf2; border-radius: 12px; overflow: hidden;
    }

    /* ---- Footer ---- */
    .app-footer {
        margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e6ebf2;
        color: #94a3b8; font-size: 0.82rem; text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1>💳 Payment Reconciliation System</h1>
    <p>Match orders against bank transactions automatically — and export a clean Excel report.</p>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def save_uploaded_file(uploaded_file) -> str:
    suffix = os.path.splitext(uploaded_file.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        return tmp.name


def try_read_csv(uploaded_file, sep=",", encoding="utf-8", nrows=None):
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file, sep=sep, encoding=encoding,
                     nrows=nrows, on_bad_lines="skip")
    uploaded_file.seek(0)
    return df


def smart_default(column_list, candidates):
    for c in candidates:
        if c in column_list:
            return column_list.index(c)
    return 0


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR – FILE UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### 📁 Upload Files")

    orders_file = st.file_uploader(
        "Orders CSV",
        type=["csv"],
        help="Your WooCommerce / shop orders export.",
    )

    st.markdown("---")
    st.markdown("### 🏦 Bank Statements")
    num_banks = st.number_input("How many bank files?", min_value=1, max_value=6,
                                value=2, step=1)
    bank_uploads = []
    for i in range(int(num_banks)):
        f = st.file_uploader(f"Bank file {i + 1}", type=["csv"],
                             key=f"bank_upload_{i}")
        if f:
            bank_uploads.append(f)

    st.markdown("---")
    st.markdown("### ⚙️ Global Filters")
    words_to_filter = st.multiselect(
        "Exclude bank rows containing these words:",
        options=["STRIPE", "Paypal", "AMAZON", "Google",
                 "STEUERVERWALTUNG", "REFUND", "GEBÜHR"],
        default=["STRIPE", "Paypal", "AMAZON", "Google", "STEUERVERWALTUNG"],
        help="Transactions from these processors are already handled elsewhere.",
    )
    payment_method = st.text_input(
        "Payment method to reconcile",
        value="bacs",
        help="Only orders with this payment method are processed (e.g. 'bacs' = bank transfer).",
    )

    st.markdown("---")
    st.markdown("### 🧠 Memory")
    use_memory = st.toggle(
        "Track unpaid orders across runs",
        value=True,
        help="Remembers unpaid orders and detects when they get paid in a later run "
             "(even from different files). Notifies you about newly-paid orders.",
    )

    st.markdown("---")
    export_filename = st.text_input("Export filename", value="reconciliation_report.xlsx")


# ══════════════════════════════════════════════════════════════════════════════
# WELCOME SCREEN (no files yet)
# ══════════════════════════════════════════════════════════════════════════════

if not orders_file:
    st.info("👈 Upload your **Orders CSV** and **Bank statement(s)** in the sidebar to get started.")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 1️⃣ Upload")
        st.write("Drop your orders CSV and one or more bank CSVs into the sidebar.")
    with col2:
        st.markdown("#### 2️⃣ Map Columns")
        st.write("Tell the app which column means what for each file.")
    with col3:
        st.markdown("#### 3️⃣ Run & Download")
        st.write("Click **Run** and download your Excel report with matched/unpaid orders.")
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 – ORDERS CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

st.markdown('<div class="step-header">Step 1 — Configure Orders File</div>',
            unsafe_allow_html=True)

try:
    orders_preview = try_read_csv(orders_file, nrows=5)
    orders_cols = list(orders_preview.columns)
except Exception as e:
    st.error(f"Could not read orders file: {e}")
    st.stop()

with st.expander("👁 Preview first 5 rows", expanded=False):
    st.dataframe(orders_preview, width="stretch")

col_l, col_r = st.columns(2)
with col_l:
    st.markdown("**Column mapping**")
    date_col        = st.selectbox("Date",            orders_cols, index=smart_default(orders_cols, ["Date","date"]))
    re_nummer_col   = st.selectbox("Receipt Number",  orders_cols, index=smart_default(orders_cols, ["Re Nummer","Re_Nummer","receipt_number"]))
    order_id_col    = st.selectbox("Order ID",        orders_cols, index=smart_default(orders_cols, ["Order ID","Order_ID","order_id"]))
    name_col        = st.selectbox("Customer Name",   orders_cols, index=smart_default(orders_cols, ["Name","name"]))
    amount_col      = st.selectbox("Amount",          orders_cols, index=smart_default(orders_cols, ["Summe","amount","Amount"]))
    pay_method_col  = st.selectbox("Payment Method",  orders_cols, index=smart_default(orders_cols, ["Zahlungsart","payment_method"]))

with col_r:
    st.markdown("**Parse settings**")
    orders_date_fmt = st.text_input("Date format", value="%d-%m-%Y", key="ord_date_fmt",
                                    help="Python strptime format, e.g. %d-%m-%Y or %Y-%m-%d")

orders_source_cfg = {
    "name": orders_file.name,
    "path": None,   # filled before pipeline run
    "columns": [date_col, re_nummer_col, order_id_col,
                name_col, amount_col, pay_method_col],
    "mapping": {
        date_col:       "date",
        re_nummer_col:  "receipt_number",
        order_id_col:   "order_id",
        name_col:       "name",
        amount_col:     "amount_paid",
        pay_method_col: "payment_method",
    },
    "parse_dates": [date_col],
    "format": orders_date_fmt,
    "payment_method_to_filter": payment_method,
}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 – BANK FILE(S) CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

st.markdown('<div class="step-header">Step 2 — Configure Bank File(s)</div>',
            unsafe_allow_html=True)

if not bank_uploads:
    st.warning("⚠️ Upload at least one bank CSV file in the sidebar.")
    st.stop()

bank_source_cfgs = []   # will hold one dict per bank file
bank_file_objects = []  # keep references for saving later

for idx, bf in enumerate(bank_uploads):
    with st.expander(f"🏦 Bank {idx + 1}: {bf.name}", expanded=(idx == 0)):
        c1, c2 = st.columns(2)
        with c1:
            sep = st.selectbox("Separator", [";", ",", "\\t"],
                               index=0, key=f"b_sep_{idx}")
        with c2:
            enc = st.selectbox("Encoding", ["cp1252", "utf-8", "latin1"],
                               index=0, key=f"b_enc_{idx}")

        actual_sep = "\t" if sep == "\\t" else sep

        try:
            bp = try_read_csv(bf, sep=actual_sep, encoding=enc, nrows=5)
            bank_cols = list(bp.columns)
            st.dataframe(bp, width="stretch")
        except Exception as e:
            st.error(f"Cannot read file with current settings: {e}")
            continue

        c3, c4 = st.columns(2)
        with c3:
            desc_col   = st.selectbox("Transaction Description", bank_cols,
                                      index=smart_default(bank_cols, ["Verwendungszweck"]),
                                      key=f"b_desc_{idx}")
            client_col = st.selectbox("Client Name", bank_cols,
                                      index=smart_default(bank_cols,
                                          ["Beguenstigter/Zahlungspflichtiger",
                                           "Name Zahlungsbeteiligter", "client_name"]),
                                      key=f"b_client_{idx}")
            amount_col_b = st.selectbox("Amount", bank_cols,
                                        index=smart_default(bank_cols, ["Betrag", "amount"]),
                                        key=f"b_amount_{idx}")
        with c4:
            booking_col = st.selectbox("Booking Date", bank_cols,
                                       index=smart_default(bank_cols, ["Buchungstag"]),
                                       key=f"b_book_{idx}")
            trans_col   = st.selectbox("Transaction Date", bank_cols,
                                       index=smart_default(bank_cols, ["Valutadatum"]),
                                       key=f"b_trans_{idx}")
            date_fmt_b  = st.text_input("Date format", value="%d-%m-%Y",
                                        key=f"b_datefmt_{idx}")

        bank_source_cfgs.append({
            "name": bf.name,
            "path": None,
            "sep": actual_sep,
            "encoding": enc,
            "columns": [desc_col, client_col, amount_col_b, booking_col, trans_col],
            "mapping": {
                desc_col:    "transaction_description",
                client_col:  "client_name",
                amount_col_b:"amount",
                booking_col: "booking_date",
                trans_col:   "transaction_date",
            },
            "parse_dates": [booking_col, trans_col],
            "format": date_fmt_b,
        })
        bank_file_objects.append(bf)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 – RUN
# ══════════════════════════════════════════════════════════════════════════════

st.markdown('<div class="step-header">Step 3 — Run Reconciliation</div>',
            unsafe_allow_html=True)

_, btn_col, _ = st.columns([1, 2, 1])
with btn_col:
    run_clicked = st.button("🚀 Run Reconciliation", type="primary",
                            width="stretch")

if run_clicked:
    if len(bank_source_cfgs) == 0:
        st.error("Configure at least one bank file first.")
    else:
        progress = st.progress(0, text="Starting…")
        status   = st.empty()
        tmp_files = []

        try:
            # -- Save uploaded files to disk --
            status.info("💾 Saving uploaded files…")
            orders_path = save_uploaded_file(orders_file)
            tmp_files.append(orders_path)
            orders_source_cfg["path"] = orders_path
            progress.progress(10, text="Files saved.")

            for i, (cfg, bf) in enumerate(zip(bank_source_cfgs, bank_file_objects)):
                p = save_uploaded_file(bf)
                cfg["path"] = p
                tmp_files.append(p)

            # -- Build pipeline config --
            config = {
                "words_to_filter": words_to_filter,
                "bank_sources":    bank_source_cfgs,
                "orders_sources":  orders_source_cfg,
            }

            from reconciliation.pipeline import ReconcilliationPipeline
            from reconciliation import exporter as exp_mod

            pipeline = ReconcilliationPipeline(config)

            if use_memory:
                store.init_db()

            status.info("📂 Loading data…")
            pipeline.load()
            progress.progress(25, text="Data loaded.")

            status.info("🧹 Cleaning data…")
            pipeline.copy()
            pipeline.clean()
            progress.progress(40, text="Data cleaned.")

            status.info("🔧 Preprocessing…")
            pipeline.preprocess_data()
            progress.progress(50, text="Preprocessing done.")

            if use_memory:
                status.info("🧠 Loading remembered unpaid orders…")
                pipeline.load_carryover()
            progress.progress(58, text="Carry-over loaded.")

            status.info("🔗 Matching by Receipt Number / Order ID…")
            pipeline.match_by_re_nummer_and_order_id()
            progress.progress(70, text="ID matching done.")

            status.info("🔍 Matching by Name + Amount + Date…")
            pipeline.match_by_name_and_amount()
            progress.progress(82, text="Fuzzy matching done.")

            if use_memory:
                status.info("🔔 Detecting newly-paid orders…")
                pipeline.detect_newly_paid()
                pipeline.save_to_db()
            progress.progress(88, text="Memory updated.")

            status.info("🔄 Restoring column names…")
            pipeline.return_original_data()
            progress.progress(92, text="Finalizing…")

            # -- Export to temp Excel --
            export_tmp = tempfile.mktemp(suffix=".xlsx")
            export_cfg = {
                "type":  "excel",
                "path":  export_tmp,
                "sheets": {
                    "Unpaid Orders":       "unmatched_orders",
                    "Matched Orders":      "matched_rows",
                    "Unmatched Payments":  "unmatched_payments",
                },
            }
            exp_mod.export_excel(pipeline, export_cfg)
            progress.progress(100, text="Done!")
            status.empty()

            # -- Read Excel bytes for download --
            with open(export_tmp, "rb") as fh:
                excel_bytes = fh.read()
            os.unlink(export_tmp)

            # -- Store in session state --
            st.session_state["results"] = {
                "matched":             pipeline.matched_rows,
                "unmatched_orders":    pipeline.unmatched_orders,
                "unmatched_payments":  pipeline.unmatched_payments,
                "newly_paid":          pipeline.newly_paid if use_memory else None,
                "excel_bytes":         excel_bytes,
            }
            st.success("✅ Reconciliation completed! Scroll down to see results.")

        except Exception as exc:
            status.empty()
            st.error(f"❌ Error: {exc}")
            with st.expander("Full traceback"):
                st.code(traceback.format_exc())
        finally:
            for p in tmp_files:
                try:
                    os.unlink(p)
                except Exception:
                    pass


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 – RESULTS
# ══════════════════════════════════════════════════════════════════════════════

if "results" in st.session_state:
    res = st.session_state["results"]

    matched    = res["matched"]
    unpaid     = res["unmatched_orders"]
    unmatched  = res["unmatched_payments"]

    n_matched   = len(matched)   if matched   is not None and not matched.empty   else 0
    n_unpaid    = len(unpaid)    if unpaid    is not None and not unpaid.empty    else 0
    n_unmatched = len(unmatched) if unmatched is not None and not unmatched.empty else 0

    st.markdown('<div class="step-header">Results</div>', unsafe_allow_html=True)

    # 🔔 Notification: orders that were unpaid in a previous run and just got paid.
    newly_paid = res.get("newly_paid")
    if newly_paid is not None and not newly_paid.empty:
        st.success(f"🔔 **{len(newly_paid)} previously-unpaid order(s) just got paid!**")
        show_cols = [c for c in ["Order Name", "Re Nummer", "Bank Amount", "Match Type"]
                     if c in newly_paid.columns]
        st.dataframe(newly_paid[show_cols] if show_cols else newly_paid,
                     width="stretch", hide_index=True)

    m1, m2, m3 = st.columns(3)
    m1.metric("✅ Matched Orders",      n_matched)
    m2.metric("❌ Unpaid Orders",       n_unpaid)
    m3.metric("🔍 Unmatched Payments",  n_unmatched)

    tab1, tab2, tab3 = st.tabs([
        f"✅ Matched Orders ({n_matched})",
        f"❌ Unpaid Orders ({n_unpaid})",
        f"🔍 Unmatched Payments ({n_unmatched})",
    ])

    with tab1:
        if n_matched:
            st.dataframe(matched, width="stretch", height=400)
        else:
            st.info("No matched orders found.")

    with tab2:
        if n_unpaid:
            st.dataframe(unpaid, width="stretch", height=400)
        else:
            st.success("🎉 All orders have been matched!")

    with tab3:
        if n_unmatched:
            st.dataframe(unmatched, width="stretch", height=400)
        else:
            st.info("No unmatched bank payments.")

    st.markdown("---")
    dl_col, _ = st.columns([1, 2])
    with dl_col:
        st.download_button(
            label="📥 Download Excel Report",
            data=res["excel_bytes"],
            file_name=export_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )

# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="app-footer">Payment Reconciliation System · '
    'Orders ↔ Bank matching · Built with Streamlit</div>',
    unsafe_allow_html=True,
)
