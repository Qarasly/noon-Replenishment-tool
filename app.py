import streamlit as st
import pandas as pd
import io
import zipfile
from datetime import datetime
import re

# --- 1. App UI Setup ---
st.set_page_config(page_title="Seller Sheet Splitter", layout="wide")
st.title("📦 Seller Data Splitter")
st.markdown("Upload your master sheet, select a category, and generate a ZIP folder of individual seller sheets.")

# --- 2. Define our Required Columns ---
# Added 'DRR' to the required raw columns
REQUIRED_COLS = [
    'sku', 'Title', 'Category', 'Live_flag', 
    'SOH_Total', 'Replenishment Qty', 'Sellers', 'DRR'
]

# Added 'Daily Run Rate' to the output (since we will rename it below)
OUTPUT_COLS_SELLER = ['sku', 'Title', 'Live_flag', 'SOH_Total', 'Replenishment Qty', 'Daily Run Rate']
OUTPUT_COLS_ALL = OUTPUT_COLS_SELLER + ['Sellers']

# Helper function to remove characters that Windows/Mac don't allow in file names
def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", str(name))

# --- 3. File Upload ---
uploaded_file = st.file_uploader("Upload Master Data (CSV or Excel)", type=['csv', 'xlsx'])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        # --- 4. Validation ---
        missing_cols = [col for col in REQUIRED_COLS if col not in df.columns]
        
        if missing_cols:
            st.error(f"⚠️ **Error:** The uploaded file is missing: {', '.join(missing_cols)}")
        else:
            st.success("Data loaded successfully!")
            
            # --- Rename the DRR column to Daily Run Rate ---
            df.rename(columns={'DRR': 'Daily Run Rate'}, inplace=True)
            
            # --- 5. Category Selection ---
            categories = df['Category'].dropna().unique().tolist()
            selected_category = st.selectbox("Select a Category to process:", options=categories)
            
            if st.button("Process Data & Create Folder"):
                with st.spinner('Generating files and zipping folder...'):
                    # Filter data
                    filtered_df = df[df['Category'] == selected_category]
                    
                    # Get today's date formatted as DD-MM