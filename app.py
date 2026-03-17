import streamlit as st
import pandas as pd
import io
import zipfile
from datetime import datetime
import re

# --- 1. App UI Setup ---
st.set_page_config(page_title="Noon Replenishment Tool", layout="wide")
st.title("📦 Noon Replenishment Tool")
st.markdown("Process master data, calculate summaries, and generate individual seller sheets.")

# --- 2. Define Required Columns ---
REQUIRED_COLS = [
    'sku', 'Title', 'Category', 'Live_flag', 
    'SOH_Total', 'Replenishment Qty', 'Sellers', 'DRR'
]

# Add a highly visible note to the user about required columns
st.info(f"**📋 Required Columns:** Your uploaded file or Google Sheet must contain the following exact headers (the order does not matter): \n\n"
        f"`{ '`, `'.join(REQUIRED_COLS) }`")

OUTPUT_COLS_SELLER = ['sku', 'Title', 'Live_flag', 'SOH_Total', 'Replenishment Qty', 'Daily Run Rate']
OUTPUT_COLS_ALL = OUTPUT_COLS_SELLER + ['Sellers', 'Category']

# Helper functions
def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", str(name))

def get_csv_url(url):
    try:
        if "export?format=csv" in url:
            return url
        sheet_id = re.search(r'/d/([a-zA-Z0-9-_]+)', url).group(1)
        gid_match = re.search(r'[#&]gid=([0-9]+)', url)
        gid = f"&gid={gid_match.group(1)}" if gid_match else ""
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv{gid}"
    except Exception:
        return None

# --- 3. Data Input Selection ---
input_method = st.radio("How would you like to provide the data?", ["
