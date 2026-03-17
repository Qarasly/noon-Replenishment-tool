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
st.info(f"**📋 Required Columns:** Your uploaded file or Google Sheet must contain the following exact headers (capitalization doesn't matter): \n\n"
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
input_method = st.radio("How would you like to provide the data?", ["Paste Google Sheet Link", "Upload a File"])

df = None 

if input_method == "Upload a File":
    uploaded_file = st.file_uploader("Upload Master Data (CSV or Excel)", type=['csv', 'xlsx'])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Error reading file: {e}")

elif input_method == "Paste Google Sheet Link":
    st.markdown("💡 *Make sure your Google Sheet sharing setting is set to **'Anyone with the link can view'**.*")
    sheet_url = st.text_input("Paste the Google Sheet URL here:")
    
    if sheet_url:
        csv_url = get_csv_url(sheet_url)
        if csv_url:
            try:
                df = pd.read_csv(csv_url)
            except Exception as e:
                st.error(f"Could not read the Google Sheet. (Error: {e})")
        else:
            st.error("Invalid Google Sheets URL. Please paste the full link.")

# --- 4. Processing the Data ---
if df is not None:
    
    # --- NEW: BULLETPROOF HEADER CLEANING ---
    # 1. Strip hidden spaces from all headers
    df.columns = df.columns.str.strip()
    
    # 2. Map whatever capitalization they used to the exact format our code needs
    rename_map = {
        'sku': 'sku',
        'title': 'Title',
        'category': 'Category',
        'live_flag': 'Live_flag',
        'soh_total': 'SOH_Total',
        'replenishment qty': 'Replenishment Qty',
        'sellers': 'Sellers',
        'drr': 'DRR'
    }
    
    # Apply the renaming instantly
    df.rename(columns={col: rename_map.get(str(col).lower(), col) for col in df.columns}, inplace=True)
    # ----------------------------------------

    missing_cols = [col for col in REQUIRED_COLS if col not in df.columns]
    
    if missing_cols:
        st.error(f"⚠️ **Error:** The data is missing the following required columns: {', '.join(missing_cols)}")
    else:
        st.success("Data loaded successfully!")
        
        # Rename DRR
        df.rename(columns={'DRR': 'Daily Run Rate'}, inplace=True)
        
        # --- 5. UI Options ---
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            categories = ["All Categories"] + df['Category'].dropna().unique().tolist()
            selected_category = st.selectbox("Select a Category to process:", options=categories)
            
        with col2:
            output_type = st.radio(
                "Select Output Type:", 
                ["Full Processing (Master File + Individual Seller Sheets)", "Summary Only (Single Excel File)"]
            )
        
        if st.button("Generate Files", type="primary"):
            with st.spinner('Processing data...'):
                
                # Filter data based on category selection
                if selected_category ==
