"""Synthetic e-commerce dataset generator with intentional dirty data."""

import numpy as np
import pandas as pd

from config import RAW_DIR

rng = np.random.default_rng(42)

N_CUSTOMERS, N_PRODUCTS, N_ORDERS = 1500, 80, 12000

REGIONS = {
    "North": ["Delhi", "Punjab", "Haryana"],
    "South": ["Karnataka", "Tamil Nadu", "Kerala"],
    "East": ["West Bengal", "Odisha", "Bihar"],
    "West": ["Maharashtra", "Gujarat", "Rajasthan"],
}

CATEGORY_PRICE = {
    "Electronics": (2000, 30000),
    "Fashion": (300, 4000),
    "Home & Kitchen": (500, 8000),
    "Books": (150, 1200),
    "Beauty": (200, 3000),
    "Sports": (400, 6000),
}

PAYMENT_METHODS = [
    "UPI", "Credit Card", "Debit Card",
    "Net Banking", "COD", "Wallet"
]


def build_customers():
    states = [(r, s) for r, sts in REGIONS.items() for s in sts]
    idx = rng.integers(0, len(states), N_CUSTOMERS)

    signup = (
        pd.Timestamp("2022-01-01")
        + pd.to_timedelta(
            rng.integers(0, 900, N_CUSTOMERS), unit="D"
        )
    )

    return pd.DataFrame({
        "customer_id": [
            f"C{i:05d}" for i in range(1, N_CUSTOMERS + 1)
        ],
        "customer_name": [
            f"Customer {i}" for i in range(1, N_CUSTOMERS + 1)
        ],
        "email": [
            f"user{i}@example.com" for i in range(1, N_CUSTOMERS + 1)
        ],
        "region": [states[i][0] for i in idx],
        "state": [states[i][1] for i in idx],
        "signup_date": signup.date,
    })


def build_products():
    cats = rng.choice(list(CATEGORY_PRICE), N_PRODUCTS)

    price = np.round([
        rng.uniform(*CATEGORY_PRICE[c]) for c in cats
    ], 2)

    cost = np.round(
        price * rng.uniform(0.55, 0.88, N_PRODUCTS), 2
    )

    return pd.DataFrame({
        "product_id": [
            f"P{i:04d}" for i in range(1, N_PRODUCTS + 1)
        ],
        "product_name": [
            f"{c} Item {i}" for i, c in enumerate(cats, 1)
        ],
        "category": cats,
        "unit_cost": cost,
        "unit_price": price,
    })


def build_sales(customers, products):
    days = pd.date_range(
        "2023-01-01", "2025-12-31", freq="D"
    )

    weight = (
        (1 + 0.002 * np.arange(len(days)))
        * np.where(days.month.isin([10, 11, 12]), 1.8, 1.0)
    )

    order_dt = (
        pd.to_datetime(
            rng.choice(days.values, N_ORDERS, p=weight / weight.sum())
        )
        + pd.to_timedelta(
            rng.integers(0, 86400, N_ORDERS), unit="s"
        )
    )

    cw = rng.pareto(1.2, len(customers)) + 1

    cust = rng.choice(
        customers.customer_id.values,
        N_ORDERS,
        p=cw / cw.sum()
    )

    region_of = dict(zip(
        customers.customer_id, customers.region
    ))

    orders = pd.DataFrame({
        "order_id": [
            f"O{i:06d}" for i in range(1, N_ORDERS + 1)
        ],
        "customer_id": cust,
        "order_date": order_dt,
        "order_status": rng.choice(
            ["Delivered", "Shipped", "Cancelled", "Returned", "Pending"],
            N_ORDERS,
            p=[0.78, 0.06, 0.07, 0.06, 0.03]
        ),
        "region": [region_of[c] for c in cust],
    })

    price_of = dict(zip(
        products.product_id, products.unit_price
    ))

    pids = products.product_id.values
    rows = []

    for oid in orders.order_id:
        for pid in rng.choice(
            pids, rng.integers(1, 5), replace=False
        ):
            qty = int(rng.integers(1, 4))
            disc = round(
                price_of[pid] * qty
                * rng.choice([0, 0, 0.05, 0.10, 0.15]),
                2
            )
            rows.append((oid, pid, qty, price_of[pid], disc))

    items = pd.DataFrame(
        rows,
        columns=[
            "order_id", "product_id", "quantity",
            "unit_price", "discount"
        ]
    )

    amount = (
        items.quantity * items.unit_price - items.discount
    ).groupby(items.order_id).sum().round(2)

    payments = pd.DataFrame({
        "payment_id": range(1, N_ORDERS + 1),
        "order_id": orders.order_id.values,
        "payment_method": rng.choice(
            PAYMENT_METHODS, N_ORDERS
        ),
        "amount": orders.order_id.map(amount).values,
        "payment_date": (
            orders.order_date
            + pd.to_timedelta(
                rng.integers(1, 30, N_ORDERS), unit="min"
            )
        ).values,
    })

    return orders, items, payments


def add_dirty_data(customers, orders, items):
    customers.loc[
        customers.sample(80, random_state=1).index, "region"
    ] = "  north "

    customers.loc[
        customers.sample(60, random_state=2).index, "email"
    ] = None

    orders.loc[
        orders.sample(120, random_state=3).index, "order_status"
    ] = "delivered "

    orders = pd.concat([
        orders, orders.sample(40, random_state=4)
    ], ignore_index=True)

    bad = items.sample(25, random_state=5).index

    items.loc[bad, "quantity"] = -items.loc[bad, "quantity"]

    return customers, orders, items


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    customers = build_customers()
    products = build_products()

    orders, items, payments = build_sales(
        customers, products
    )

    customers, orders, items = add_dirty_data(
        customers, orders, items
    )

    tables = {
        "customers": customers,
        "products": products,
        "orders": orders,
        "order_items": items,
        "payments": payments
    }

    for name, df in tables.items():
        df.to_csv(RAW_DIR / f"{name}.csv", index=False)
        print(f"{name}: {len(df):,} rows")


if __name__ == "__main__":
    main()