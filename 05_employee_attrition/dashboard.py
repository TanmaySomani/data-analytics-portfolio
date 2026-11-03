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
total = df[df.industry == "Total, all industries"].iloc[0]
industries = df[df.industry != "Total, all industries"].sort_values("aug_2026_quits_rate_pct", ascending=False)
selected = st.sidebar.multiselect("Industries to compare", industries.industry.tolist(), default=industries.industry.head(5).tolist())
measure = st.sidebar.radio("Display", ["Compare both years", "Change in percentage points"])
view = industries[industries.industry.isin(selected)].copy()
no_data(view)
metrics([("Industries selected", f"{len(view):,}"), ("Highest Aug 2026", f"{view.aug_2026_quits_rate_pct.max():.1f}%"),
         ("Lowest Aug 2026", f"{view.aug_2026_quits_rate_pct.min():.1f}%"), ("All-industry Aug 2026", f"{total.aug_2026_quits_rate_pct:.1f}%")])
st.info("Monthly, seasonally adjusted industry estimates. August 2026 was preliminary when published. Quits are voluntary separations, not all employee departures.")
if measure == "Compare both years":
    long = view.melt(id_vars="industry", value_vars=["aug_2025_quits_rate_pct", "aug_2026_quits_rate_pct"], var_name="period", value_name="rate_pct")
    long["period"] = long.period.map({"aug_2025_quits_rate_pct":"August 2025", "aug_2026_quits_rate_pct":"August 2026 (preliminary)"})
    fig = px.bar(long, x="rate_pct", y="industry", color="period", barmode="group", orientation="h", labels={"rate_pct":"Monthly quits rate (%)", "industry":"Industry"})
    fig.update_layout(yaxis={"categoryorder":"total ascending"})
else:
    fig = px.bar(view.sort_values("change_pp"), x="change_pp", y="industry", orientation="h", labels={"change_pp":"Change from 2025 to 2026 (percentage points)", "industry":"Industry"})
chart(fig)
st.subheader("Published industry estimates")
st.caption("The all-industry rate is shown as a benchmark above and is excluded from the selected-industry ranking. Rates should not be summed or averaged without employment weights.")
st.dataframe(view, hide_index=True)
csv_download(view, "selected_industry_quits.csv")
context()
