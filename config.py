
import os
import tempfile
from pathlib import Path

import streamlit as st
from sqlalchemy import URL

BASE_DIR = Path(__file__).resolve().parent

# Project folders
RAW_DIR = BASE_DIR / "data" / "raw"
CLEAN_DIR = BASE_DIR / "data" / "clean"
REPORT_DIR = BASE_DIR / "reports"

SCHEMA_FILE = BASE_DIR / "sql" / "schema.sql"


# Read settings from Streamlit Secrets or local environment
def get_setting(key, default=""):
    try:
        value = st.secrets.get(key)
        if value is not None:
            return value
    except Exception:
        pass

    return os.getenv(key, default)


MYSQL_USER = get_setting("MYSQL_USER", "avnadmin")
MYSQL_PASSWORD = get_setting("MYSQL_PASSWORD")
MYSQL_HOST = get_setting(
    "MYSQL_HOST",
    "mysql-1001088c-smart-expense-tracker-vedant-2026.k.aivencloud.com"
)
MYSQL_PORT = int(get_setting("MYSQL_PORT", "18720"))
MYSQL_DB = get_setting("MYSQL_DB", "ecommerce_bi")


# SSL certificate: Streamlit Secrets on cloud, local file on PC
CA_CERT_CONTENT = get_setting("MYSQL_CA_CERT")

if CA_CERT_CONTENT:
    CA_CERT_FILE = Path(tempfile.gettempdir()) / "ecommerce_bi_ca.pem"
    CA_CERT_FILE.write_text(CA_CERT_CONTENT.strip() + "\n", encoding="utf-8")
else:
    CA_CERT_FILE = BASE_DIR / "ca.pem"


# Database URL
DB_URL = URL.create(
    drivername="mysql+pymysql",
    username=MYSQL_USER,
    password=MYSQL_PASSWORD,
    host=MYSQL_HOST,
    port=MYSQL_PORT,
    database=MYSQL_DB
)
