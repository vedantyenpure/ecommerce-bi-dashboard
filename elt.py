
"""Clean raw CSVs with Pandas and load them into Aiven MySQL."""

import ssl
import pandas as pd
from sqlalchemy import create_engine, text

from config import (
    CLEAN_DIR,
    DB_URL,
    RAW_DIR,
    SCHEMA_FILE,
    CA_CERT_FILE
)


def title_clean(series, default):
    return (
        series.astype("string")
        .str.strip()
        .str.title()
        .fillna(default)
        .astype(object)
    )


def clean_all():
    raw = {
        n: pd.read_csv(RAW_DIR / f"{n}.csv")
        for n in [
            "customers", "products", "orders",
            "order_items", "payments"
        ]
    }

    cust = raw["customers"].drop_duplicates("customer_id").copy()
    cust["customer_name"] = cust["customer_name"].str.strip()
    cust["region"] = title_clean(cust["region"], "Unknown")
    cust["state"] = title_clean(cust["state"], "Unknown")
    cust["email"] = (
        cust["email"]
        .fillna("not_provided@unknown.com")
        .str.strip()
        .str.lower()
    )
    cust["signup_date"] = pd.to_datetime(
        cust["signup_date"], errors="coerce"
    )

    prod = raw["products"].drop_duplicates("product_id").copy()
    prod["category"] = title_clean(prod["category"], "Other")
    prod = prod[
        (prod.unit_price > 0)
        & (prod.unit_cost >= 0)
        & (prod.unit_cost <= prod.unit_price)
    ]

    ords = raw["orders"].drop_duplicates("order_id").copy()
    ords["order_date"] = pd.to_datetime(
        ords["order_date"], errors="coerce"
    )
    ords = ords.dropna(subset=["order_date"])
    ords["order_status"] = title_clean(
        ords["order_status"], "Pending"
    )
    ords["region"] = title_clean(ords["region"], "Unknown")
    ords = ords[ords.customer_id.isin(cust.customer_id)]

    items = raw["order_items"].copy()
    items = items[
        (items.quantity > 0) & (items.unit_price > 0)
    ]
    items["discount"] = (
        items["discount"].fillna(0).clip(lower=0)
    )
    items = items[
        items.order_id.isin(ords.order_id)
        & items.product_id.isin(prod.product_id)
    ]
    items = items.drop_duplicates(
        ["order_id", "product_id"]
    ).drop(columns=["item_id"], errors="ignore")

    pays = raw["payments"].drop_duplicates("payment_id").copy()
    pays = pays[
        (pays.amount > 0)
        & pays.order_id.isin(ords.order_id)
    ]
    pays["payment_method"] = title_clean(
        pays["payment_method"], "Unknown"
    )
    pays["payment_date"] = pd.to_datetime(
        pays["payment_date"], errors="coerce"
    )

    frames = {
        "customers": cust,
        "products": prod,
        "orders": ords,
        "order_items": items,
        "payments": pays
    }

    for name, df in frames.items():
        print(
            f"{name}: raw={len(raw[name]):,} "
            f"clean={len(df):,}"
        )

    return frames


def load_to_mysql(frames):

    # SSL certificate verification
    ssl_context = ssl.create_default_context(
        cafile=str(CA_CERT_FILE)
    )

    # Connect to Aiven database
    engine = create_engine(
        DB_URL,
        connect_args={"ssl": ssl_context}
    )

    # Create database tables using schema.sql
    statements = [
        s.strip()
        for s in SCHEMA_FILE.read_text(
            encoding="utf-8"
        ).split(";")
        if s.strip()
    ]

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))

    print("Database tables created successfully.")

    # Load cleaned data into MySQL
    for name in [
        "customers", "products", "orders",
        "order_items", "payments"
    ]:
        frames[name].to_sql(
            name,
            engine,
            if_exists="append",
            index=False,
            chunksize=2000,
            method="multi"
        )

        print(f"{name} loaded successfully.")

    engine.dispose()


def main():
    frames = clean_all()

    CLEAN_DIR.mkdir(parents=True, exist_ok=True)

    for name, df in frames.items():
        df.to_csv(
            CLEAN_DIR / f"{name}.csv",
            index=False
        )

    load_to_mysql(frames)

    print("ETL complete: clean data loaded into Aiven MySQL.")


if __name__ == "__main__":
    main()
