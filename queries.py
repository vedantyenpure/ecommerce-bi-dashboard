"""Database connection and advanced SQL analysis queries."""

from functools import lru_cache

import pandas as pd
from sqlalchemy import create_engine

from config import DB_URL


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(DB_URL, pool_pre_ping=True)


def load_lines(engine):
    return pd.read_sql(
        "SELECT * FROM v_order_lines",
        engine,
        parse_dates=["order_date"]
    )


SQL_QUERIES = {
    "monthly_growth": """
        WITH monthly AS (
            SELECT order_month,
                   SUM(net_sales) AS revenue,
                   SUM(profit) AS profit
            FROM v_order_lines
            WHERE is_revenue = 1
            GROUP BY order_month
        )
        SELECT order_month,
               ROUND(revenue, 2) AS revenue,
               ROUND(profit, 2) AS profit,
               ROUND(LAG(revenue) OVER w, 2)
                   AS prev_month_revenue,
               ROUND(
                   (revenue - LAG(revenue) OVER w)
                   / NULLIF(LAG(revenue) OVER w, 0) * 100,
                   2
               ) AS mom_growth_pct,
               ROUND(
                   SUM(revenue) OVER (
                       PARTITION BY LEFT(order_month, 4)
                       ORDER BY order_month
                   ), 2
               ) AS ytd_revenue
        FROM monthly
        WINDOW w AS (ORDER BY order_month);
    """,

    "rfm": """
        WITH customer_rfm AS (
            SELECT customer_id,
                   DATEDIFF(
                       (SELECT MAX(order_date) FROM orders),
                       MAX(order_date)
                   ) AS recency_days,
                   COUNT(DISTINCT order_id) AS frequency,
                   ROUND(SUM(net_sales), 2) AS monetary
            FROM v_order_lines
            WHERE is_revenue = 1
            GROUP BY customer_id
        ),
        scored AS (
            SELECT *,
                   NTILE(5) OVER (
                       ORDER BY recency_days DESC
                   ) AS r_score,
                   NTILE(5) OVER (
                       ORDER BY frequency ASC
                   ) AS f_score,
                   NTILE(5) OVER (
                       ORDER BY monetary ASC
                   ) AS m_score
            FROM customer_rfm
        )
        SELECT customer_id, recency_days, frequency, monetary,
               r_score, f_score, m_score,
               CONCAT(r_score, f_score, m_score) AS rfm_code
        FROM scored
        ORDER BY monetary DESC
        LIMIT 500;
    """,

    "product_rank": """
        SELECT category,
               product_name,
               ROUND(SUM(net_sales), 2) AS revenue,
               ROUND(SUM(profit), 2) AS profit,
               ROUND(
                   SUM(profit) / NULLIF(SUM(net_sales), 0) * 100,
                   2
               ) AS margin_pct,
               RANK() OVER (
                   PARTITION BY category
                   ORDER BY SUM(net_sales) DESC
               ) AS rank_in_category
        FROM v_order_lines
        WHERE is_revenue = 1
        GROUP BY category, product_name
        ORDER BY category, rank_in_category;
    """,

    "region_share": """
        SELECT region,
               ROUND(SUM(net_sales), 2) AS revenue,
               ROUND(
                   SUM(net_sales) / SUM(SUM(net_sales)) OVER () * 100,
                   2
               ) AS share_pct,
               ROUND(
                   SUM(profit) / NULLIF(SUM(net_sales), 0) * 100,
                   2
               ) AS margin_pct
        FROM v_order_lines
        WHERE is_revenue = 1
        GROUP BY region
        ORDER BY revenue DESC;
    """,

    "cohort": """
        WITH first_orders AS (
            SELECT customer_id,
                   MIN(order_month) AS cohort_month
            FROM v_order_lines
            WHERE is_revenue = 1
            GROUP BY customer_id
        ),
        activity AS (
            SELECT DISTINCT
                   v.customer_id,
                   v.order_month,
                   f.cohort_month
            FROM v_order_lines v
            JOIN first_orders f
                ON f.customer_id = v.customer_id
            WHERE v.is_revenue = 1
        )
        SELECT cohort_month,
               TIMESTAMPDIFF(
                   MONTH,
                   STR_TO_DATE(
                       CONCAT(cohort_month, '-01'), '%Y-%m-%d'
                   ),
                   STR_TO_DATE(
                       CONCAT(order_month, '-01'), '%Y-%m-%d'
                   )
               ) AS month_index,
               COUNT(DISTINCT customer_id) AS active_customers
        FROM activity
        GROUP BY cohort_month, month_index
        ORDER BY cohort_month, month_index;
    """
}


def run_query(name, engine=None):
    engine = engine or get_engine()
    return pd.read_sql(SQL_QUERIES[name], engine)