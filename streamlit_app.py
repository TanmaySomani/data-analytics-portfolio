"""One Streamlit app with navigation across the five portfolio dashboards."""
import streamlit as st

pages = [
    st.Page("01_sales_performance/dashboard.py", title="Sales performance", icon="📈", default=True),
    st.Page("02_customer_churn/dashboard.py", title="Customer churn", icon="📉", url_path="customer-churn"),
    st.Page("03_marketing_campaigns/dashboard.py", title="Marketing campaigns", icon="📣", url_path="marketing"),
    st.Page("04_ecommerce_customers/dashboard.py", title="E-commerce customers", icon="🛍️", url_path="ecommerce"),
    st.Page("05_employee_attrition/dashboard.py", title="Employee attrition", icon="👥", url_path="employee-attrition"),
]
st.navigation(pages).run()
