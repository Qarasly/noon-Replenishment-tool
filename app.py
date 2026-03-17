import streamlit as st
import pandas as pd
import io
import zipfile
from datetime import datetime
import re

# --- 1. App UI Setup ---
st.set_page_config(page_title="Seller Sheet Splitter", layout="wide")
st.title("📦 Seller Data Splitter")
st.markdown("Provide your master data, select a category, and generate a ZIP folder of individual seller sheets.")

# --- 2. Define our Required Columns ---
REQUIRED_COLS = [
    'sku', 'Title', 'Category', 'Live_flag', 
    'SOH_Total', 'Replenishment Qty', 'Sellers', 'DRR'
]

OUTPUT_COLS_SELLER = ['sku', 'Title', 'Live_flag', 'SOH_Total', 'Replenishment Qty', 'Daily Run Rate']
OUTPUT_COLS_ALL = OUTPUT_COLS_SELLER + ['Sellers']

# Helper functions
def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", str(name))

def get_csv_url(url):
    """Converts a standard Google Sheets URL into a direct CSV download URL."""
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
# Let the user choose how they want to provide the data
input_method = st.radio("How would you like to provide the data?", ["Paste Google Sheet Link", "Upload a File"])

df = None # This will hold our data regardless of how it's loaded

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
    st.info("💡 Make sure your Google Sheet sharing setting is set to **'Anyone with the link can view'**.")
    sheet_url = st.text_input("Paste the Google Sheet URL here:")
    
    if sheet_url:
        csv_url = get_csv_url(sheet_url)
        if csv_url:
            try:
                # Pandas can read directly from a CSV URL!
                df = pd.read_csv(csv_url)
            except Exception as e:
                st.error(f"Could not read the Google Sheet. Please double-check the link and ensure sharing is set to 'Anyone with the link'. (Error: {e})")
        else:
            st.error("Invalid Google Sheets URL. Please paste the full link.")

# --- 4. Processing the Data ---
# If we successfully loaded the dataframe (df) from either method, proceed:
if df is not None:
    # Validation
    missing_cols = [col for col in REQUIRED_COLS if col not in df.columns]
    
    if missing_cols:
        st.error(f"⚠️ **Error:** The data is missing the following required columns: {', '.join(missing_cols)}")
    else:
        st.success("Data loaded successfully!")
        
        # Rename the DRR column to Daily Run Rate
        df.rename(columns={'DRR': 'Daily Run Rate'}, inplace=True)
        
        # --- 5. Category Selection ---
        categories = df['Category'].dropna().unique().tolist()
        selected_category = st.selectbox("Select a Category to process:", options=categories)
        
        if st.button("Process Data & Create Folder"):
            with st.spinner('Generating files and zipping folder...'):
                # Filter data
                filtered_df = df[df['Category'] == selected_category]
                
                # Get today's date formatted as DD-MM
                current_date = datetime.now().strftime("%d-%m")
                
                # Define the main folder name
                safe_category = clean_filename(selected_category)
                folder_name = f"{safe_category} replenishment _ {current_date}"
                
                # Create an in-memory ZIP file
                zip_buffer = io.BytesIO()
                
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    
                    # 1. Create and write the "Whole Category" sheet
                    cat_file_name = f"{safe_category} Replenishment {current_date}.xlsx"
                    cat_buffer = io.BytesIO() 
                    
                    filtered_df[OUTPUT_COLS_ALL].to_excel(cat_buffer, index=False)
                    zip_file.writestr(f"{folder_name}/{cat_file_name}", cat_buffer.getvalue())
                    
                    # 2. Loop through sellers and create their individual sheets
                    unique_sellers = filtered_df['Sellers'].dropna().unique()
                    
                    for seller in unique_sellers:
                        seller_df = filtered_df[filtered_df['Sellers'] == seller]
                        safe_seller = clean_filename(seller)
                        
                        seller_file_name = f"{safe_seller} replenishment_{current_date}.xlsx"
                        seller_buffer = io.BytesIO()
                        
                        seller_df[OUTPUT_COLS_SELLER].to_excel(seller_buffer, index=False)
                        zip_file.writestr(f"{folder_name}/{seller_file_name}", seller_buffer.getvalue())
                
                # --- 6. Download Button ---
                st.success("Folder generated! Click below to download your ZIP file.")
                st.download_button(
                    label="📥 Download ZIP Folder",
                    data=zip_buffer.getvalue(),
                    file_name=f"{folder_name}.zip",
                    mime="application/zip"
                )
