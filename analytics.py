
"""Business analytics: KPIs, trends, RFM, cohorts, forecast and recommendations."""
import numpy as np
import pandas as pd

Z_95 = 1.96


def _revenue(df):
    return df[df.is_revenue == 1]


def kpis(df):
    rev = _revenue(df)
    revenue, profit = rev.net_sales.sum(), rev.profit.sum()
    orders, customers = rev.order_id.nunique(), rev.customer_id.nunique()
    return {
        "Revenue": revenue,
        "Profit": profit,
        "Margin %": profit / revenue * 100 if revenue else 0.0,
        "Orders": orders,
        "Customers": customers,
        "Avg Order Value": revenue / orders if orders else 0.0,
    }


def monthly_trend(df):
    m = _revenue(df).groupby("order_month").agg(
        revenue=("net_sales", "sum"),
        profit=("profit", "sum"),
        orders=("order_id", "nunique"),
    ).reset_index()
    m["mom_growth_pct"] = m.revenue.pct_change() * 100
    m["yoy_growth_pct"] = m.revenue.pct_change(12) * 100
    return m


def yearly_summary(df):
    rev = _revenue(df).assign(year=lambda x: x.order_month.str[:4])
    y = rev.groupby("year").agg(
        revenue=("net_sales", "sum"),
        profit=("profit", "sum")
    ).reset_index()
    y["yoy_growth_pct"] = y.revenue.pct_change() * 100
    return y


def group_perf(df, by):
    g = _revenue(df).groupby(by).agg(
        revenue=("net_sales", "sum"),
        profit=("profit", "sum"),
        units=("quantity", "sum"),
    ).reset_index()
    g["margin_pct"] = g.profit / g.revenue * 100
    g["revenue_share_pct"] = g.revenue / g.revenue.sum() * 100
    return g.sort_values("revenue", ascending=False).reset_index(drop=True)


def _segment(row):
    r, f, m = row.R, row.F, row.M
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r >= 3 and f >= 3:
        return "Loyal Customers"
    if r >= 4 and f <= 2:
        return "New Customers"
    if r <= 2 and f >= 3:
        return "At Risk"
    if r <= 2 and f <= 2 and m <= 2:
        return "Lost"
    return "Needs Attention"


def rfm_segments(df):
    rev = _revenue(df)
    if rev.empty:
        return pd.DataFrame()
    snapshot = rev.order_date.max() + pd.Timedelta(days=1)
    rfm = rev.groupby("customer_id").agg(
        last_order=("order_date", "max"),
        frequency=("order_id", "nunique"),
        monetary=("net_sales", "sum"),
    ).reset_index()
    rfm["recency"] = (snapshot - rfm.last_order).dt.days
    if len(rfm) >= 5:
        rank = lambda s: s.rank(method="first")
        rfm["R"] = pd.qcut(
            rank(rfm.recency), 5, labels=[5, 4, 3, 2, 1]
        ).astype(int)
        rfm["F"] = pd.qcut(
            rank(rfm.frequency), 5, labels=[1, 2, 3, 4, 5]
        ).astype(int)
        rfm["M"] = pd.qcut(
            rank(rfm.monetary), 5, labels=[1, 2, 3, 4, 5]
        ).astype(int)
    else:
        rfm["R"] = rfm["F"] = rfm["M"] = 3
    rfm["score"] = rfm.R + rfm.F + rfm.M
    rfm["segment"] = rfm.apply(_segment, axis=1)
    return rfm.sort_values(
        "monetary", ascending=False
    ).reset_index(drop=True)


def _month_index(s):
    return s.str[:4].astype(int) * 12 + s.str[5:7].astype(int)


def cohort_retention(df):
    rev = _revenue(df).copy()
    if rev.empty:
        return pd.DataFrame()
    cohort = rev.groupby("customer_id").order_month.min().rename("cohort")
    rev = rev.join(cohort, on="customer_id")
    rev["period"] = (
        _month_index(rev.order_month) - _month_index(rev.cohort)
    )
    pivot = rev.groupby(
        ["cohort", "period"]
    ).customer_id.nunique().unstack(fill_value=0)
    return (pivot.divide(pivot[0], axis=0) * 100).round(1)


def forecast_revenue(monthly, periods=6):
    empty = pd.DataFrame(
        columns=["order_month", "forecast", "lower", "upper"]
    )
    s = monthly.set_index("order_month")["revenue"].astype(float)
    if len(s) < 12:
        return empty
    t = np.arange(len(s))
    slope, intercept = np.polyfit(t, s.values, 1)
    trend = intercept + slope * t
    months = pd.PeriodIndex(s.index, freq="M").month
    seas = pd.Series(
        s.values / trend, index=months
    ).groupby(level=0).mean()
    seas = seas.reindex(range(1, 13)).fillna(1.0)
    seas = seas / seas.mean()
    fitted = trend * seas.reindex(months).values
    sigma = np.std(s.values - fitted, ddof=1)
    fut_t = np.arange(len(s), len(s) + periods)
    fut_periods = pd.period_range(
        pd.Period(s.index[-1], freq="M") + 1,
        periods=periods,
        freq="M"
    )
    fut = (
        intercept + slope * fut_t
    ) * seas.reindex(fut_periods.month).values
    return pd.DataFrame({
        "order_month": fut_periods.strftime("%Y-%m"),
        "forecast": fut.round(2),
        "lower": np.clip(fut - Z_95 * sigma, 0, None).round(2),
        "upper": (fut + Z_95 * sigma).round(2),
    })


def recommendations(df, monthly, cat, reg, rfm, retention, fc):
    tips = []
    top = cat.iloc[0]
    tips.append(
        f"Category '{top.category}' contributes "
        f"{top.revenue_share_pct:.1f}% of revenue; "
        "protect its stock levels and use bundle offers "
        "to raise average order value."
    )

    weak = cat.sort_values("margin_pct").iloc[0]
    if weak.margin_pct < 15:
        tips.append(
            f"Category '{weak.category}' has a thin margin "
            f"of {weak.margin_pct:.1f}%; review supplier costs "
            "and limit discount depth."
        )
    else:
        tips.append(
            f"Lowest-margin category '{weak.category}' still "
            f"earns {weak.margin_pct:.1f}%; keep monitoring "
            "discount leakage."
        )

    if len(reg) > 1:
        low = reg.sort_values("margin_pct").iloc[0]
        tips.append(
            f"Region '{low.region}' has the lowest margin "
            f"({low.margin_pct:.1f}%); consider region-specific "
            "delivery cost optimisation."
        )

    if len(monthly) >= 4:
        avg3 = monthly.mom_growth_pct.tail(3).mean()
        if avg3 < 0:
            tips.append(
                f"Revenue declined by {avg3:.1f}% MoM on average "
                "over the last 3 months; launch a seasonal campaign "
                "and audit the conversion funnel."
            )
        else:
            tips.append(
                f"Revenue grew {avg3:.1f}% MoM on average over "
                "the last 3 months; scale the channels behind this growth."
            )

    if not rfm.empty:
        at_risk = rfm.segment.isin(["At Risk", "Lost"]).mean() * 100
        champs = (rfm.segment == "Champions").mean() * 100
        tips.append(
            f"{at_risk:.1f}% of customers are At Risk or Lost; "
            "run win-back offers. "
            f"Champions ({champs:.1f}%) are ideal for referral "
            "and VIP programmes."
        )

    if not retention.empty and 1 in retention.columns:
        m1 = retention[1].mean()
        if m1 < 25:
            tips.append(
                f"Average month-1 retention is only {m1:.1f}%; "
                "offer a second-purchase incentive within 30 days "
                "of the first order."
            )
        else:
            tips.append(
                f"Average month-1 retention is {m1:.1f}%; "
                "test loyalty rewards to push it further."
            )

    if not fc.empty:
        n = len(fc)
        next_total = fc.forecast.sum()
        last_total = monthly.revenue.tail(n).sum()
        chg = (next_total / last_total - 1) * 100 if last_total else 0.0
        tips.append(
            f"Forecast for the next {n} months is {next_total:,.0f} "
            f"({chg:+.1f}% vs the last {n} months); "
            "use it to plan inventory and marketing budgets."
        )

    orders = df.drop_duplicates("order_id")
    bad = orders.order_status.isin(["Cancelled", "Returned"]).mean() * 100
    tips.append(
        f"{bad:.1f}% of orders were cancelled or returned; "
        "check fulfilment accuracy and product descriptions "
        "to reduce this leakage."
    )
    return tips


def run_all(df, periods=6):
    monthly = monthly_trend(df)
    cat = group_perf(df, "category")
    reg = group_perf(df, "region")
    rfm = rfm_segments(df)
    retention = cohort_retention(df)
    fc = forecast_revenue(monthly, periods)
    return {
        "kpi": kpis(df),
        "monthly": monthly,
        "yearly": yearly_summary(df),
        "cat": cat,
        "prod": group_perf(df, ["category", "product_name"]),
        "reg": reg,
        "rfm": rfm,
        "retention": retention,
        "fc": fc,
        "recs": recommendations(
            df, monthly, cat, reg, rfm, retention, fc
        ),
    }
