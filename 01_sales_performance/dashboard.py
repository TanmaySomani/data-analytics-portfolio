from pathlib import Path
import json
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
with (ROOT / "outputs" / "summary.json").open(encoding="utf-8") as file:
    META = json.load(file)
st.set_page_config(page_title=META["title"], page_icon="📊", layout="wide")
st.title(META["title"])
st.caption(META["grain"])
st.sidebar.header("Explore the data")

@st.cache_data(show_spinner="Loading the project data...")
def read_cached(path, modified_ns, **kwargs):
    return pd.read_csv(path, **kwargs)

def load_csv(name, **kwargs):
    path = ROOT / name
    if not path.exists():
        st.error(f"Missing {name}. Run python3 project.py from this project folder first.")
        st.stop()
    return read_cached(str(path), path.stat().st_mtime_ns, **kwargs)

def chart(fig):
    fig.update_layout(margin=dict(l=10, r=15, t=30, b=10), height=360,
                      colorway=["#087f8c", "#e09f3e", "#607d8b"],
                      legend_title_text="")
    st.plotly_chart(fig)

def metrics(items):
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        col.metric(label, value)

def csv_download(frame, filename):
    st.download_button("Download this table as CSV", frame.to_csv(index=False).encode("utf-8"),
                       file_name=filename, mime="text/csv")

def context():
    with st.expander("Source, definitions and limitations"):
        st.write(META["citation"])
        st.markdown(f"[Source documentation]({META['source']})")
        for definition in META["definitions"]:
            st.write("• " + definition)
        st.warning(META["caveats"])
    st.caption("Calculated from the included cleaned dataset. Filters change the figures shown; source explanations and presentations describe the full analysis.")

def no_data(frame):
    if frame.empty:
        st.warning("No records match these filters. Broaden your selection to see results.")
        context()
        st.stop()

df = load_csv("data/clean.csv.gz", dtype={"InvoiceNo":"string", "StockCode":"string", "CustomerID":"string"})
months = sorted(df["month"].dropna().unique().tolist())
start, end = st.sidebar.select_slider("Invoice month", options=months, value=(months[0], months[-1]))
country = st.sidebar.selectbox("Customer country", ["All countries"] + sorted(df["Country"].dropna().unique().tolist()))
query = st.sidebar.text_input("Stock code or description contains", help="Optional text search; it is not a product-category filter.").strip()
view = df[df["month"].between(start, end)]
if country != "All countries":
    view = view[view["Country"] == country]
if query:
    mask = view["StockCode"].fillna("").str.contains(query, case=False, regex=False) | view["Description"].fillna("").str.contains(query, case=False, regex=False)
    view = view[mask]
no_data(view)
metrics([("Included line value", f"£{view.line_value.sum():,.0f}"), ("Invoices", f"{view.InvoiceNo.nunique():,}"),
         ("Sales lines", f"{len(view):,}"), ("Identified customers", f"{view.CustomerID.nunique():,}")])
st.info("Positive invoice-line value excludes cancellations and nonpositive lines. It is not profit or net revenue; some codes represent fees or postage.")
monthly = view.groupby("month", as_index=False).agg(line_value=("line_value", "sum"), lines=("InvoiceNo", "size"))
markets = view.groupby("Country", as_index=False).agg(line_value=("line_value", "sum"), lines=("InvoiceNo", "size"), invoices=("InvoiceNo", "nunique")).sort_values("line_value", ascending=False)
products = view.groupby(["StockCode", "Description"], dropna=False, as_index=False).agg(line_value=("line_value", "sum"), units=("Quantity", "sum"), lines=("InvoiceNo", "size")).sort_values("line_value", ascending=False)
a, b = st.columns(2)
with a:
    st.subheader("Included value by month")
    chart(px.line(monthly, x="month", y="line_value", markers=True, labels={"month":"Invoice month", "line_value":"Included line value (£)"}))
with b:
    st.subheader("Top countries")
    chart(px.bar(markets.head(10).sort_values("line_value"), x="line_value", y="Country", orientation="h", hover_data=["lines", "invoices"], labels={"line_value":"Included line value (£)", "Country":"Country"}))
st.subheader("Highest-value stock codes")
st.caption("Codes can include non-product charges; inspect descriptions before drawing product conclusions.")
st.dataframe(products.head(20), hide_index=True)
csv_download(products, "filtered_stock_codes.csv")
context()
