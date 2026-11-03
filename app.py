
import io

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import analytics as an
from queries import SQL_QUERIES, get_engine, load_lines, run_query
from reports import build_excel, build_pdf

st.set_page_config(
    page_title="E-Commerce BI",
    page_icon="📊",
    layout="wide"
)


@st.cache_data(ttl=600, show_spinner="MySQL वरून data load होत आहे...")
def fetch_lines():
    return load_lines(get_engine())


lines = fetch_lines()

# Sidebar filters
st.sidebar.header("🔎 Filters")

min_d = lines.order_date.min().date()
max_d = lines.order_date.max().date()

picked = st.sidebar.date_input(
    "Order date range",
    (min_d, max_d),
    min_value=min_d,
    max_value=max_d
)

start, end = (
    (picked[0], picked[1])
    if len(picked) == 2
    else (picked[0], picked[0])
)

all_regions = sorted(lines.region.unique())
all_cats = sorted(lines.category.unique())

sel_regions = st.sidebar.multiselect(
    "Region", all_regions, default=all_regions
)
sel_cats = st.sidebar.multiselect(
    "Category", all_cats, default=all_cats
)

day = lines.order_date.dt.date

df = lines[
    (day >= start)
    & (day <= end)
    & lines.region.isin(sel_regions)
    & lines.category.isin(sel_cats)
]

if df.empty:
    st.warning("निवडलेल्या filters साठी data उपलब्ध नाही.")
    st.stop()

res = an.run_all(df)

kpi = res["kpi"]
monthly = res["monthly"]
yearly = res["yearly"]

st.title("📊 E-Commerce Sales & Business Intelligence")
st.caption(
    f"Period: {start} to {end} | "
    f"Orders in view: {df.order_id.nunique():,}"
)

t1, t2, t3, t4, t5, t6, t7, t8, t9 = st.tabs([
    "📈 Overview",
    "🗓️ Growth",
    "👥 RFM Segments",
    "🛍️ Products",
    "🌍 Regions",
    "🔁 Retention",
    "🔮 Forecast",
    "🗄️ SQL Insights",
    "💡 Recommendations",
])

# Overview
with t1:
    cols = st.columns(len(kpi))

    for col, (label, val) in zip(cols, kpi.items()):
        col.metric(
            label,
            f"{val:.1f}%" if label == "Margin %" else f"{val:,.0f}"
        )

    st.plotly_chart(
        px.line(
            monthly,
            x="order_month",
            y=["revenue", "profit"],
            markers=True,
            title="Monthly Revenue vs Profit"
        ),
        use_container_width=True
    )

    c1, c2 = st.columns(2)

    c1.plotly_chart(
        px.pie(
            res["cat"],
            names="category",
            values="revenue",
            hole=0.45,
            title="Revenue by Category"
        ),
        use_container_width=True
    )

    c2.plotly_chart(
        px.bar(
            res["reg"],
            x="region",
            y="revenue",
            color="margin_pct",
            title="Revenue by Region"
        ),
        use_container_width=True
    )

# Growth
with t2:
    st.plotly_chart(
        px.bar(
            yearly,
            x="year",
            y="revenue",
            text_auto=".2s",
            title="Yearly Revenue"
        ),
        use_container_width=True
    )

    st.plotly_chart(
        px.bar(
            monthly,
            x="order_month",
            y="mom_growth_pct",
            title="Month-over-Month Growth %"
        ),
        use_container_width=True
    )

    st.dataframe(yearly)

# RFM Segments
with t3:
    rfm = res["rfm"]

    seg = rfm.groupby("segment").agg(
        customers=("customer_id", "count"),
        revenue=("monetary", "sum")
    ).reset_index()

    c1, c2 = st.columns(2)

    c1.plotly_chart(
        px.bar(
            seg,
            x="segment",
            y="customers",
            color="segment",
            title="Customers by RFM Segment"
        ),
        use_container_width=True
    )

    c2.plotly_chart(
        px.scatter(
            rfm,
            x="recency",
            y="monetary",
            color="segment",
            size="frequency",
            log_y=True,
            title="Recency vs Monetary"
        ),
        use_container_width=True
    )

    st.dataframe(
        rfm[
            [
                "customer_id", "recency", "frequency",
                "monetary", "R", "F", "M", "score", "segment"
            ]
        ].head(200)
    )

# Products
with t4:
    st.plotly_chart(
        px.treemap(
            res["prod"].head(60),
            path=["category", "product_name"],
            values="revenue",
            color="margin_pct",
            title="Product Revenue (Top 60)"
        ),
        use_container_width=True
    )

    st.dataframe(res["prod"].head(20))

# Regions
with t5:
    st.plotly_chart(
        px.bar(
            res["reg"],
            x="region",
            y=["revenue", "profit"],
            barmode="group",
            title="Revenue vs Profit by Region"
        ),
        use_container_width=True
    )

    st.dataframe(res["reg"])

# Retention
with t6:
    ret = res["retention"].iloc[:, :13]

    if ret.empty:
        st.info("Retention विश्लेषणासाठी पुरेसा data नाही.")
    else:
        st.plotly_chart(
            px.imshow(
                ret,
                text_auto=".0f",
                aspect="auto",
                color_continuous_scale="Blues",
                labels=dict(
                    x="Months since first order",
                    y="Cohort",
                    color="Retention %"
                ),
                title="Cohort Retention (%)"
            ),
            use_container_width=True
        )

# Forecast
with t7:
    horizon = st.slider(
        "Forecast horizon (months)",
        3, 12, 6
    )

    fc = an.forecast_revenue(
        monthly,
        periods=horizon
    )

    fig = go.Figure()

    fig.add_scatter(
        x=monthly.order_month,
        y=monthly.revenue,
        name="Actual"
    )

    if not fc.empty:
        fig.add_scatter(
            x=fc.order_month,
            y=fc.upper,
            line=dict(width=0),
            showlegend=False
        )

        fig.add_scatter(
            x=fc.order_month,
            y=fc.lower,
            fill="tonexty",
            name="95% band",
            fillcolor="rgba(31,78,121,0.15)",
            line=dict(width=0)
        )

        fig.add_scatter(
            x=fc.order_month,
            y=fc.forecast,
            name="Forecast",
            line=dict(dash="dash", color="orange")
        )

        st.dataframe(fc)

    else:
        st.info(
            "Forecast साठी किमान 12 महिन्यांचा data आवश्यक आहे."
        )

    st.plotly_chart(fig, use_container_width=True)

# SQL Insights
with t8:
    name = st.selectbox(
        "SQL query निवडा",
        list(SQL_QUERIES)
    )

    st.code(SQL_QUERIES[name], language="sql")
    st.dataframe(run_query(name))

# Recommendations and reports
with t9:
    for tip in res["recs"]:
        st.markdown(f"- {tip}")

    tables = {
        "Monthly": monthly,
        "Yearly": yearly,
        "Category": res["cat"],
        "Product": res["prod"],
        "Region": res["reg"],
        "RFM": res["rfm"],
        "Forecast": res["fc"]
    }

    xbuf = io.BytesIO()
    build_excel(xbuf, tables)

    pbuf = io.BytesIO()
    build_pdf(
        pbuf,
        "E-Commerce Business Report",
        kpi,
        monthly,
        res["recs"]
    )

    c1, c2 = st.columns(2)

    c1.download_button(
        "⬇️ Download Excel Report",
        xbuf.getvalue(),
        file_name="ecommerce_report.xlsx"
    )

    c2.download_button(
        "⬇️ Download PDF Report",
        pbuf.getvalue(),
        file_name="ecommerce_report.pdf",
        mime="application/pdf"
    )
