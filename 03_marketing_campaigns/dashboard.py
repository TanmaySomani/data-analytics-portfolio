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
method = st.sidebar.selectbox("Contact method", ["All methods"] + sorted(df.contact.dropna().unique().tolist()))
prior = st.sidebar.selectbox("Previous campaign outcome", ["All outcomes"] + sorted(df.poutcome.dropna().unique().tolist()))
contact_band = st.sidebar.selectbox("Contacts in current campaign", ["All contact counts", "1", "2", "3", "4+"])
view = df
if method != "All methods": view = view[view.contact == method]
if prior != "All outcomes": view = view[view.poutcome == prior]
if contact_band != "All contact counts": view = view[view.contact_band.astype(str) == contact_band]
no_data(view)
metrics([("Campaign records", f"{len(view):,}"), ("Subscriptions", f"{int(view.converted.sum()):,}"),
         ("Subscription rate", f"{view.converted.mean():.1%}"), ("Contact methods", f"{view.contact.nunique():,}")])
st.info("These are historical phone-campaign records, not unique customer counts. Spend and incremental lift are unavailable; group differences are not causal.")
group_label = st.selectbox("Compare subscription rate by", ["Contact method", "Previous campaign outcome", "Contacts in current campaign", "Last contact month"])
group = {"Contact method":"contact", "Previous campaign outcome":"poutcome", "Contacts in current campaign":"contact_band", "Last contact month":"month"}[group_label]
summary = view.groupby(group, dropna=False).agg(records=("converted", "size"), subscriptions=("converted", "sum")).reset_index()
summary["subscription_rate_pct"] = summary.subscriptions / summary.records * 100
order = {"month":["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"], "contact_band":["1","2","3","4+"]}
if group in order: summary[group] = pd.Categorical(summary[group].astype(str), order[group], ordered=True); summary = summary.sort_values(group)
chart(px.bar(summary, x=group, y="subscription_rate_pct", text_auto=".1f", hover_data=["records", "subscriptions"], labels={"subscription_rate_pct":"Subscription rate (%)", group:group_label}))
st.subheader("Segment detail")
st.caption("Each rate divides subscription records by all records in that segment. Last-contact months combine years.")
st.dataframe(summary, hide_index=True)
csv_download(summary, "filtered_campaign_segments.csv")
context()
