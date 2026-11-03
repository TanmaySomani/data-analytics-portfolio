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

df = load_csv("data/clean.csv.gz")
tariff = st.sidebar.selectbox("Tariff", ["All tariffs", "Pay as you go", "Contractual"])
complaint = st.sidebar.selectbox("Complaint", ["All customers", "Complaint recorded", "No complaint"])
low, high = st.sidebar.slider("Subscription length (months)", int(df["Subscription Length"].min()), int(df["Subscription Length"].max()), (int(df["Subscription Length"].min()), int(df["Subscription Length"].max())))
view = df[df["Subscription Length"].between(low, high)]
if tariff != "All tariffs": view = view[view["Tariff Plan"] == (1 if tariff == "Pay as you go" else 2)]
if complaint != "All customers": view = view[view["Complains"] == (1 if complaint == "Complaint recorded" else 0)]
no_data(view)
metrics([("Customers", f"{len(view):,}"), ("Churn labels", f"{int(view.Churn.sum()):,}"),
         ("Churn rate", f"{view.Churn.mean():.1%}"), ("Recorded complaints", f"{int(view.Complains.sum()):,}")])
st.info("Associations are descriptive and do not establish why a customer churned. Features cover the first nine months and the outcome is measured at month 12.")
group_label = st.selectbox("Compare churn by", ["Complaint status", "Tariff plan", "Subscription length band"])
cols = {"Complaint status":"Complains", "Tariff plan":"Tariff Plan", "Subscription length band":"tenure_band"}
group = cols[group_label]
summary = view.groupby(group, dropna=False).agg(customers=("Churn", "size"), churned=("Churn", "sum")).reset_index()
summary["churn_rate_pct"] = summary.churned / summary.customers * 100
if group == "Complains": summary[group] = summary[group].map({0:"No complaint", 1:"Complaint"})
if group == "Tariff Plan": summary[group] = summary[group].map({1:"Pay as you go", 2:"Contractual"})
if group == "tenure_band": summary[group] = pd.Categorical(summary[group], ["0–6", "7–12", "13–24", "25+"], ordered=True); summary = summary.sort_values(group)
chart(px.bar(summary, x=group, y="churn_rate_pct", text_auto=".1f", hover_data=["customers", "churned"], labels={"churn_rate_pct":"Churn rate (%)", group:group_label}))
st.subheader("Segment detail")
st.caption("Rates use the customer count within each displayed segment; small groups can be unstable.")
st.dataframe(summary, hide_index=True)
csv_download(summary, "filtered_churn_segments.csv")
context()
