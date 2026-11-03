#!/usr/bin/env python3
"""Analyze the included observed dataset. Requires Python 3.9+ and pandas."""
from pathlib import Path
import hashlib,json
import pandas as pd
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'; OUT=ROOT/'outputs'; OUT.mkdir(exist_ok=True)
KIND='ecommerce'

def write(df,name): df.to_csv(OUT/(name+'.csv'),index=False)
def percent(x): return f'{100*x:.1f}%'
def money(x): return f'£{x:,.0f}'
def group_binary(df,col,target):
    x=df.groupby(col,dropna=False).agg(records=(target,'size'),events=(target,'sum')).reset_index().rename(columns={col:'segment'})
    x['rate']=x.events/x.records
    return x.sort_values('rate',ascending=False)
def save_data(df): df.to_csv(DATA/'clean.csv.gz',index=False,compression='gzip')
def hash_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def retail():
    d=pd.read_csv(DATA/'raw.csv.gz',dtype={'InvoiceNo':'string','StockCode':'string','CustomerID':'string'},parse_dates=['InvoiceDate'])
    n=len(d); missing_id=int(d.CustomerID.isna().sum()); dup=int(d.duplicated().sum())
    canceled=d.InvoiceNo.str.upper().str.startswith('C',na=False); nonpos=(d.Quantity<=0)|(d.UnitPrice<=0); excluded=int((canceled|nonpos).sum())
    ok=d[~(canceled|nonpos)].copy(); ok['line_value']=ok.Quantity*ok.UnitPrice; ok['month']=ok.InvoiceDate.dt.to_period('M').astype(str)
    quality=f'{n:,} source lines; {int(canceled.sum()):,} cancellation-prefixed lines; {int(nonpos.sum()):,} nonpositive quantity or price lines; {excluded:,} excluded by either rule; {missing_id:,} source lines lack customer ID. These categories overlap. {dup:,} exact duplicate-looking rows are retained because they may represent distinct invoice lines.'
    return d,ok,quality

def run():
    if KIND=='sales':
        raw,d,quality=retail(); save_data(d)
        country=d.groupby('Country',dropna=False).agg(lines=('InvoiceNo','size'),invoice_count=('InvoiceNo','nunique'),sales_value=('line_value','sum')).sort_values('sales_value',ascending=False).reset_index()
        product=d.groupby(['StockCode','Description'],dropna=False).agg(lines=('InvoiceNo','size'),units=('Quantity','sum'),sales_value=('line_value','sum')).sort_values('sales_value',ascending=False).reset_index()
        monthly=d.groupby('month').agg(lines=('InvoiceNo','size'),invoice_count=('InvoiceNo','nunique'),sales_value=('line_value','sum')).reset_index()
        cust=d.dropna(subset=['CustomerID']).groupby('CustomerID').agg(invoice_count=('InvoiceNo','nunique'),sales_value=('line_value','sum')).sort_values('sales_value',ascending=False).reset_index()
        for name,table in [('country_summary',country),('product_summary',product),('monthly_summary',monthly),('customer_summary',cust)]:write(table,name)
        top=country.iloc[0]; total=d.line_value.sum(); invoices=d.InvoiceNo.nunique(); top_p=product.iloc[0]; months=monthly.sort_values('sales_value',ascending=False)
        metrics=[('Positive line value',money(total)),('Invoices',f'{invoices:,}'),('Sales lines',f'{len(d):,}'),('Countries',f'{len(country):,}')]
        findings=[f"{top['Country']} accounts for {percent(top.sales_value/total)} of included line value.",f"The highest-value stock code is {top_p.StockCode}, at {money(top_p.sales_value)}.",f"{months.iloc[0]['month']} has the largest included line value at {money(months.iloc[0].sales_value)}."]
        chart=('Included line value by country',country.head(5).Country.astype(str).tolist(),[round(x/1e6,2) for x in country.head(5).sales_value],'£ millions')
        problem='How did an online retailer’s observed invoice-line value vary by country, product and month?'
        grain='One row per invoice line for a UK-based online retailer, 1 Dec 2010 to 9 Dec 2011. The company sells gifts and includes wholesale customers.'
        definitions=['Included line value = Quantity × UnitPrice in pounds, restricted to non-cancellation lines with positive quantity and unit price.','Invoices = distinct InvoiceNo among included lines; it is not necessarily a count of unique customers.','Country share = included country line value ÷ all included line value.','Monthly comparisons use calendar months; December 2010 and December 2011 are incomplete.']
        caveats='This is positive invoice-line value, not net revenue: cancelled and negative lines are excluded rather than matched back to orders. Prices and amounts may include postage, fees and unusual adjustments. There is no product cost, so profit, margin and loss-making products cannot be computed. The dataset is historical and from a single retailer.'
        action='Review high-value products and markets with the retailer’s returns, product costs and fulfilment data before deciding where to change pricing or inventory.'
        steps=['Reconcile invoices, cancellations and credit notes with accounting records.','Join product cost, delivery fees and returns to calculate contribution margin.','Investigate seasonal demand using complete comparable months and more years of data.']
        citation='Chen, D. (2015), Online Retail, UCI Machine Learning Repository, https://doi.org/10.24432/C5BW33 (CC BY 4.0).'
        source='https://archive.ics.uci.edu/dataset/352/online+retail'
        dictionary=['InvoiceNo: invoice identifier; a C prefix indicates cancellation.','StockCode and Description: product code and source description.','Quantity and UnitPrice: line quantity and unit price in pounds.','InvoiceDate: transaction date and time.','CustomerID: customer identifier, missing on some lines; Country: customer country.','line_value and month: derived in this project.']
    elif KIND=='churn':
        d=pd.read_csv(DATA/'raw.csv'); d.columns=[' '.join(c.split()) for c in d.columns]; n=len(d); quality=f'{n:,} customer rows; {int(d.isna().sum().sum()):,} missing cells; {int(d.duplicated().sum()):,} identical feature rows retained because the dataset provides no unique customer identifier.'
        d['tenure_band']=pd.cut(d['Subscription Length'],bins=[-1,6,12,24,10000],labels=['0–6','7–12','13–24','25+']).astype(str); save_data(d)
        complaint=group_binary(d,'Complains','Churn'); tariff=group_binary(d,'Tariff Plan','Churn'); tenure=group_binary(d,'tenure_band','Churn')
        for name,t in [('complaint_summary',complaint),('tariff_summary',tariff),('tenure_summary',tenure)]:write(t,name)
        c0=complaint[complaint.segment==0].iloc[0];c1=complaint[complaint.segment==1].iloc[0]; total=int(d.Churn.sum())
        metrics=[('Customers',f'{n:,}'),('Churn labels',f'{total:,}'),('Observed churn rate',percent(total/n)),('With complaint',f'{int((d.Complains==1).sum()):,}')]
        findings=[f"Customers with a recorded complaint had {percent(c1.rate)} churn versus {percent(c0.rate)} without one.",f"Pay-as-you-go tariff group (code 1) has {percent(tariff[tariff.segment==1].iloc[0].rate)} churn.",f"The dataset identifies {total:,} churned customers among {n:,} records."]
        chart=('Churn rate by complaint status',['No complaint','Complaint'],[round(c0.rate*100,1),round(c1.rate*100,1)],'Customers marked churned (%)')
        problem='Which customer characteristics are associated with churn in an observed telecom customer sample?'
        grain='One customer per record from an Iranian telecom company. Features aggregate the first nine months; the label records customer status at the end of 12 months.'
        definitions=['Churn rate = number with Churn = 1 ÷ number of customer records in the segment.','Complains: 1 indicates a complaint; 0 indicates no complaint.','Tariff Plan: 1 = pay as you go; 2 = contractual.','Subscription length bands use 0–6, 7–12, 13–24 and 25+ months.']
        caveats='The data is a sample from one telecom provider and the collection calendar is not specified. Complaint, usage and tariff associations do not prove why customers leave; selection and other differences may explain them. Status may contain outcome-related information, so review its timing before predictive use. Customer Value has an unspecified calculation and is not treated as revenue.'
        action='Investigate service issues behind complaints, then test a support intervention with a randomized holdout and measure incremental retention.'
        steps=['Validate event definitions, the label construction and feature timing with the source owner.','Compare complaint and churn associations within tariff and tenure bands.','Run a randomized intervention with a measured cost and a pre-specified retention outcome.']
        citation='Iranian Churn (2020), UCI Machine Learning Repository, https://doi.org/10.24432/C5JW3Z (CC BY 4.0).'
        source='https://archive.ics.uci.edu/dataset/563/iranian+churn+dataset'
        dictionary=['Churn: binary outcome (1 churn; 0 non-churn).','Complains: binary complaint indicator.','Subscription Length: total months of subscription.','Tariff Plan: 1 pay as you go; 2 contractual.','Call Failure, Seconds of Use, Frequency of use and Frequency of SMS: observed service measures.','Status: source active/non-active code; Customer Value: source-calculated value with unspecified formula.']
    elif KIND=='marketing':
        d=pd.read_csv(DATA/'raw.csv',sep=';'); n=len(d); quality=f'{n:,} campaign records; {int(d.isna().sum().sum()):,} blank cells; {int((d=="unknown").sum().sum()):,} source values labeled unknown. {int(d.duplicated().sum()):,} identical-looking rows retained because there is no customer ID or event ID.'
        d['converted']=(d.y=='yes').astype(int);d['contact_band']=pd.cut(d.campaign,bins=[0,1,2,3,1000],labels=['1','2','3','4+']).astype(str);save_data(d)
        channel=group_binary(d,'contact','converted');previous=group_binary(d,'poutcome','converted');contact=group_binary(d,'contact_band','converted');month=group_binary(d,'month','converted')
        for name,t in [('channel_summary',channel),('previous_outcome_summary',previous),('contact_frequency_summary',contact),('month_summary',month)]:write(t,name)
        yes=int(d.converted.sum()); cell=channel[channel.segment=='cellular'].iloc[0];tele=channel[channel.segment=='telephone'].iloc[0]; prev=previous[previous.segment=='success'].iloc[0]
        metrics=[('Campaign records',f'{n:,}'),('Subscriptions',f'{yes:,}'),('Subscription rate',percent(yes/n)),('Contact methods','2')]
        findings=[f"{percent(cell.rate)} of cellular records and {percent(tele.rate)} of telephone records ended in subscription.",f"Records with prior campaign success have {percent(prev.rate)} subscription rate ({int(prev.records):,} records).",f"Overall, {yes:,} of {n:,} records indicate a term-deposit subscription."]
        chart=('Subscription rate by contact method',channel.segment.tolist(),[round(x*100,1) for x in channel.rate],'Share of records subscribing (%)')
        problem='How do observed term-deposit subscription rates differ across bank telemarketing records?'
        grain='One campaign example in the bank-additional-full.csv sample of a Portuguese bank, May 2008 to November 2010. Multiple contacts can be required for one client.'
        definitions=['Subscription rate = records with y = yes ÷ all records in the segment.','Contact is the recorded communication type; campaign counts contacts for the client during the current campaign.','Previous outcome describes the previous campaign and includes a nonexistent category.','Rates are record-weighted; without customer IDs, unique customers and independent customer-level conversion cannot be calculated.']
        caveats='The source records phone campaigns, not paid search or social. It has no spend, revenue, cost or randomized assignment: CPA, ROAS and incremental effect cannot be computed. Channel and previous-campaign comparisons are observational and may reflect targeting or economic conditions. Last-call duration is known only after a call and must not be used for pre-call targeting. The data is historical.'
        action='Use the differences to design a prospective, randomized channel or contact-strategy test, recording costs, eligibility and incremental subscriptions.'
        steps=['Check campaign eligibility and contact histories before comparing audience groups.','Avoid using call duration as a predictor before the call; review sensitive attributes and fair treatment.','Randomize a channel strategy and collect spend and margin before estimating incremental ROI.']
        citation='Moro, S., Rita, P., & Cortez, P. (2014), Bank Marketing, UCI Machine Learning Repository, https://doi.org/10.24432/C5K306 (CC BY 4.0).'
        source='https://archive.ics.uci.edu/dataset/222/bank+marketing'
        dictionary=['y: whether the client subscribed to a term deposit.','contact: communication type (cellular or telephone).','campaign: number of contacts in the current campaign for the client.','poutcome: prior campaign outcome.','month and day_of_week: timing of last contact; year is not included.','duration: last contact duration in seconds, only available after contact.','converted and contact_band: derived in this project.']
    elif KIND=='ecommerce':
        raw,d,quality=retail(); without=int(d.CustomerID.isna().sum()); d=d.dropna(subset=['CustomerID']).copy();save_data(d)
        # A purchase is a distinct customer/invoice combination. Aggregate lines before measuring repeat.
        orders=d.groupby(['CustomerID','InvoiceNo'],as_index=False).agg(order_date=('InvoiceDate','min'),order_value=('line_value','sum'))
        orders['order_day']=orders.order_date.dt.normalize(); maxdate=d.InvoiceDate.max().normalize(); first=orders.groupby('CustomerID').order_day.min().rename('first_day'); orders=orders.join(first,on='CustomerID')
        orders['days_since_first']=(orders.order_day-orders.first_day).dt.days
        cust=orders.groupby('CustomerID').agg(first_day=('first_day','first'),orders=('InvoiceNo','nunique'),spend=('order_value','sum')).reset_index()
        repeat=orders[(orders.days_since_first<=90)].groupby('CustomerID').InvoiceNo.nunique().rename('orders_90d');cust=cust.join(repeat,on='CustomerID');cust['eligible_90d']=cust.first_day<=maxdate-pd.Timedelta(days=90);cust['repeat_90d']=(cust.orders_90d>=2);cust['cohort']=cust.first_day.dt.to_period('M').astype(str)
        eligible=cust[cust.eligible_90d].copy();cohort=eligible.groupby('cohort').agg(customers=('CustomerID','size'),repeat_customers=('repeat_90d','sum')).reset_index();cohort['repeat_rate']=cohort.repeat_customers/cohort.customers
        frequency=cust.groupby('orders').agg(customers=('CustomerID','size'),spend=('spend','sum')).reset_index();write(orders,'order_summary');write(cust,'customer_summary');write(cohort,'eligible_cohort_summary');write(frequency,'frequency_summary')
        rate=eligible.repeat_90d.mean(); avg=orders.order_value.mean(); total=len(cust)
        metrics=[('Identified customers',f'{total:,}'),('Identified invoices',f'{len(orders):,}'),('Average invoice value',f'£{avg:,.2f}'),('90-day repeat rate',percent(rate))]
        findings=[f"{int(eligible.repeat_90d.sum()):,} of {len(eligible):,} eligible customers made a second observed invoice within 90 calendar days.",f"Average identified invoice value was £{avg:,.2f}, excluding cancellation and nonpositive lines.",f"{without:,} otherwise qualifying lines lack customer IDs and are excluded from customer analysis."]
        chart=('90-day repeat rate by first observed month',cohort.cohort.tolist(),[round(x*100,1) for x in cohort.repeat_rate],'Eligible customers repeating (%)')
        problem='How often did identifiable customers place another invoice within a comparable 90-day observation period?'
        grain='The source is invoice-line data from a UK online retailer, 1 Dec 2010 to 9 Dec 2011. This analysis groups positive lines into customer/invoice purchases.'
        quality+=f' Among otherwise qualifying lines, {without:,} lack customer ID and are excluded from customer metrics.'
        definitions=['An order is a distinct CustomerID and InvoiceNo combination in the cleaned data.','Average invoice value = total included line value for identified customers ÷ distinct identified customer/invoice orders.','First observed purchase is the earliest included invoice in this dataset, not necessarily a lifetime first purchase.','90-day repeat rate = eligible customers with at least two distinct invoices by 90 calendar days after first observed purchase ÷ eligible customers.','Eligible means first observed purchase is at least 90 calendar days before the final observed date. Same-day distinct invoices count.']
        caveats='Only identified transactions are included. The dataset has no pre-window customer history, and the source is a gift retailer with wholesale customers. Cancellation and negative lines are excluded without matching to original invoices, so values are not net of returns. Observed repeat is not lifetime retention; customers may place orders outside the data window.'
        action='Test a post-purchase message using a randomized holdout and track 90-day repeat purchases and contribution margin among eligible customers.'
        steps=['Reconcile returns and join earlier order history to distinguish new customers from first observed customers.','Compare mature cohorts over equal follow-up windows and segment wholesale accounts separately.','Randomize a retention intervention and measure incremental gross profit after message costs.']
        citation='Chen, D. (2015), Online Retail, UCI Machine Learning Repository, https://doi.org/10.24432/C5BW33 (CC BY 4.0).'
        source='https://archive.ics.uci.edu/dataset/352/online+retail'
        dictionary=['InvoiceNo and CustomerID: identifiers used to construct a customer/invoice order.','InvoiceDate: date and time of the transaction.','Quantity and UnitPrice: invoice-line quantity and unit price in pounds.','line_value: Quantity × UnitPrice for qualifying lines.','first_day, eligible_90d and repeat_90d: derived customer-level fields in outputs/customer_summary.csv.']
    else:
        d=pd.read_csv(DATA/'raw.csv');d['change_pp']=d.aug_2026_quits_rate_pct-d.aug_2025_quits_rate_pct;save_data(d);write(d.sort_values('aug_2026_quits_rate_pct',ascending=False),'industry_summary')
        sub=d[d.industry!='Total, all industries']; hi=sub.loc[sub.aug_2026_quits_rate_pct.idxmax()];lo=sub.loc[sub.aug_2026_quits_rate_pct.idxmin()];total=d[d.industry=='Total, all industries'].iloc[0]; r=sub[sub.industry=='Retail trade'].iloc[0]
        metrics=[('Total quits rate',f'{total.aug_2026_quits_rate_pct:.1f}%'),('Highest industry',f'{hi.aug_2026_quits_rate_pct:.1f}%'),('Lowest industry',f'{lo.aug_2026_quits_rate_pct:.1f}%'),('Reference month','Aug 2026')]
        findings=[f"{hi.industry} has the highest listed quits rate at {hi.aug_2026_quits_rate_pct:.1f}%.",f"{lo.industry} has the lowest listed rate at {lo.aug_2026_quits_rate_pct:.1f}%.",f"Retail trade increased {r.change_pp:+.1f} percentage points from August 2025 to August 2026."]
        chart=('Monthly quits rates by industry',sub.head(5).industry.tolist(),sub.head(5).aug_2026_quits_rate_pct.tolist(),'Quits as % of employment')
        problem='How do U.S. voluntary separation rates vary by industry, and where should an employer benchmark retention?'
        grain='One published industry-level, seasonally adjusted quits-rate comparison for August 2025 and August 2026. The 2026 estimates were preliminary when published.'
        quality=f'{len(d)} transcribed table rows, including one all-industry total; source values are seasonally adjusted rates. All {len(d)} rows have both published comparison values. The total is excluded from the industry ranking.'
        definitions=['Monthly quits rate = number of quits during the month ÷ employment × 100, as defined by BLS.','Quits are generally voluntary separations and exclude retirements and transfers to other locations.','Year-over-year change is August 2026 rate minus August 2025 rate, in percentage points.','These are monthly, seasonally adjusted survey estimates, not annual employee turnover rates.']
        caveats='This is a small manually transcribed extract of a BLS table, not individual-level employee data. It cannot identify reasons for leaving, employee characteristics or causal factors. The latest month was preliminary at publication; estimates can be revised and survey uncertainty matters. Industry comparisons do not control for workforce composition.'
        action='Compare an organization’s own monthly voluntary quits with the closest industry benchmark and investigate differences using confidential aggregate employee feedback.'
        steps=['Align the organization’s quits definition, month and denominator with the BLS definition.','Compare against the closest industry over a longer series, accounting for sample uncertainty.','Use aggregated exit feedback and a voluntary intervention to test actionable hypotheses.']
        citation='U.S. Bureau of Labor Statistics, The Economics Daily, “Quits rate 3.5 percent in accommodation and food services, August 2026,” 13 October 2026.'
        source='https://www.bls.gov/opub/ted/2026/quits-rate-3-5-percent-in-accommodation-and-food-services-august-2026.htm'
        dictionary=['industry: published industry grouping or all-industry total.','aug_2026_quits_rate_pct: seasonally adjusted monthly quits rate, preliminary at publication.','aug_2025_quits_rate_pct: corresponding published rate one year earlier.','change_pp: 2026 rate minus 2025 rate, in percentage points.']
    title={'sales':'Sales Performance Analysis','churn':'Customer Churn Analysis','marketing':'Marketing Campaign Analysis','ecommerce':'E-commerce Customer Analysis','attrition':'Employee Attrition Analysis'}[KIND]
    payload=dict(kind=KIND,title=title,metrics=metrics,findings=findings,action=action,chart=dict(title=chart[0],categories=chart[1],values=chart[2],unit=chart[3]),problem=problem,grain=grain,definitions=definitions,caveats=caveats,nextsteps=steps,quality=quality,citation=citation,source=source)
    (OUT/'summary.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    rawfile=DATA/('raw.csv.gz' if KIND in ('sales','ecommerce') else 'raw.csv')
    explanation=[f'# {title}: project explanation','', '## 1. Business question',problem,'','## 2. Source and scope',citation,'',f'Source documentation: {source}', '',grain,'',f'Included raw file: `{rawfile.name}`. SHA-256: `{hash_file(rawfile)}`.']
    if KIND in ('sales','ecommerce'):explanation+=['','The included compressed CSV is a conversion of the original UCI workbook. Both retail projects use the same source for different questions; they are not independent datasets.']
    if KIND=='attrition':explanation+=['','The CSV is a manually transcribed extract of the source table, restricted to the published industry rows and the all-industry total. It is a snapshot of figures as published, not a live feed.']
    explanation+=['','## 3. Data dictionary']+['- '+x for x in dictionary]
    explanation+=['','## 4. Cleaning and quality checks',quality,'','Review `data/clean.csv.gz` for the analytical records. Duplicate-looking records are not removed without a reliable event identifier. `unknown` categories are retained where present. Quality rules are explicit in `project.py`.','', '## 5. Metrics and definitions']+['- '+x for x in definitions]
    explanation+=['','## 6. Results','| Metric | Value |','|---|---:|']+[f'| {k} | {v} |' for k,v in metrics]
    explanation+=['','### Findings']+[f'{i}. {x}' for i,x in enumerate(findings,1)]
    explanation+=['','Detailed segment counts and values are in `outputs/`. Percentages in text and slides are rounded; CSVs retain greater precision.','', '## 7. Recommendation',action,'','### Next steps']+[f'{i}. {x}' for i,x in enumerate(steps,1)]
    explanation+=['','## 8. Limitations and interpretation',caveats,'','These findings describe the supplied historical data; they should not be presented as results for another company or as causal effects.','', '## 9. Reproduce the analysis','1. Install Python 3.9+ and the dependency: `python3 -m pip install -r requirements.txt`.','2. From the project folder, run `python3 project.py`. The included source file is read locally; no network connection is needed.','3. Review `outputs/summary.json`, the segment CSVs and `data/clean.csv.gz`. Re-running overwrites generated outputs and this explanation but preserves the raw source file.','4. Open `presentation.pptx`. The deck is a snapshot of this analysis and is not automatically regenerated by `project.py`.','', '## 10. Interview discussion','Describe the business question and source first. State the denominator and observation window before comparing rates, explain the biggest data limitation, and describe what experiment or additional source would support the next decision.','']
    explanation.extend(['', *'## 11. Run the interactive dashboard\n\nFrom a terminal opened in this project folder, create and activate a virtual environment, then install the dependencies:\n\n```bash\npython3 -m venv .venv\nsource .venv/bin/activate\npython -m pip install -r requirements.txt\n```\n\nOn Windows, activate the environment with `.venv\\Scripts\\activate` instead. The initial installation requires internet access. Then start the dashboard:\n\n```bash\npython -m streamlit run dashboard.py --server.address 127.0.0.1\n```\n\nOpen the local URL printed in the terminal (normally `http://localhost:8501`). Stop the server with Ctrl+C. To run another dashboard at the same time, use a different port, for example append `--server.port 8502`. The dashboard reads the included local files and does not need internet access after installation. If an analysis output is missing, run `python project.py` first.\n\nFilter customers by first observed purchase month and total observed invoices. The repeat-rate chart uses only customers with a complete 90-day observation window. Restricting total invoices selects customers using later behavior, so the resulting repeat rate describes that selected group only. Download the eligible cohort table as CSV.\n\nChanges to filter selections affect the dashboard only. Run `python project.py` to rebuild the cleaned data and analysis outputs from the included source; the dashboard detects the updated files. The presentation remains a separate snapshot and is not rebuilt by the dashboard or analysis script.\n'.splitlines()])
    (ROOT/'PROJECT_EXPLANATION.md').write_text('\n'.join(explanation),encoding='utf8')
    print(title+': analysis complete')
if __name__=='__main__':run()
