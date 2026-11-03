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

customers = load_csv("outputs/customer_summary.csv", dtype={"CustomerID":"string"})
orders = load_csv("outputs/order_summary.csv", dtype={"CustomerID":"string", "InvoiceNo":"string"})
cohorts = sorted(customers.cohort.dropna().unique().tolist())
start, end = st.sidebar.select_slider("First observed purchase month", options=cohorts, value=(cohorts[0], cohorts[-1]))
min_orders, max_orders = int(customers.orders.min()), int(customers.orders.max())
order_min, order_max = st.sidebar.slider("Total observed invoices per customer", min_orders, max_orders, (min_orders, max_orders))
view = customers[customers.cohort.between(start, end) & customers.orders.between(order_min, order_max)]
no_data(view)
filtered_orders = orders[orders.CustomerID.isin(view.CustomerID)]
eligible = view[view.eligible_90d]
repeat = f"{eligible.repeat_90d.mean():.1%}" if len(eligible) else "Not available"
aov = f"£{filtered_orders.order_value.mean():,.2f}" if len(filtered_orders) else "Not available"
metrics([("Identified customers", f"{len(view):,}"), ("Invoices", f"{len(filtered_orders):,}"),
         ("Average invoice value", aov), ("90-day repeat rate", repeat)])
st.info(f"90-day repeat uses {len(eligible):,} eligible customers with a full follow-up window. Restricting total observed invoices creates a selected group, so its repeat rate is not representative of all customers.")
cohort = eligible.groupby("cohort", as_index=False).agg(customers=("CustomerID", "size"), repeat_customers=("repeat_90d", "sum"))
if not cohort.empty:
    cohort["repeat_rate_pct"] = 100 * cohort.repeat_customers / cohort.customers
    st.subheader("Repeat purchase by first observed month")
    chart(px.bar(cohort, x="cohort", y="repeat_rate_pct", hover_data=["customers", "repeat_customers"], labels={"cohort":"First observed month", "repeat_rate_pct":"90-day repeat rate (%)"}))
    st.dataframe(cohort, hide_index=True)
    csv_download(cohort, "filtered_eligible_cohorts.csv")
else:
    st.warning("This selection contains no customers with a complete 90-day follow-up.")
st.subheader("Observed purchase frequency")
freq = view.groupby("orders", as_index=False).agg(customers=("CustomerID", "size"))
chart(px.bar(freq.head(20), x="orders", y="customers", labels={"orders":"Invoices per customer", "customers":"Customers"}))
st.caption("The frequency chart shows the first 20 observed invoice counts; the customer and invoice totals above include all selected counts.")
context()
