import streamlit as st
import pandas as pd
import io
import zipfile
from datetime import datetime
import re

# --- 1. App UI Setup ---
st.set_page_config(page_title="Seller Data Splitter", layout="wide")
st.title("📦 Seller Data Splitter & Summarizer")
st.markdown("Process master data, calculate summaries, and generate individual seller sheets.")

# --- 2. Define Required Columns ---
REQUIRED_COLS = [
    'sku', 'Title', 'Category', 'Live_flag', 
    'SOH_Total', 'Replenishment Qty', 'Sellers', 'DRR'
]

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
    st.info("💡 Make sure your Google Sheet sharing setting is set to **'Anyone with the link can view'**.")
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
    missing_cols = [col for col in REQUIRED_COLS if col not in df.columns]
    
    if missing_cols:
        st.error(f"⚠️ **Error:** The data is missing the following required columns: {', '.join(missing_cols)}")
    else:
        st.success("Data loaded successfully!")
        
        # Rename DRR
        df.rename(columns={'DRR': 'Daily Run Rate'}, inplace=True)
        
        # --- 5. UI Options ---
        col1, col2 = st.columns(2)
        
        with col1:
            categories = ["All Categories"] + df['Category'].dropna().unique().tolist()
            selected_category = st.selectbox("Select a Category to process:", options=categories)
            
        with col2:
            output_type = st.radio(
                "Select Output Type:", 
                ["Full Processing (Master File + Individual Seller Sheets)", "Summary Only (Single Excel File)"]
            )
        
        if st.button("Generate Files"):
            with st.spinner('Processing data...'):
                
                # Filter data based on category selection
                if selected_category == "All Categories":
                    filtered_df = df.copy()
                    safe_category = "All_Categories"
                else:
                    filtered_df = df[df['Category'] == selected_category].copy()
                    safe_category = clean_filename(selected_category)
                
                current_date = datetime.now().strftime("%d-%m")
                folder_name = f"{safe_category} replenishment _ {current_date}"
                
                # --- EXPLODE SELLERS ---
                exploded_df = filtered_df.copy()
                exploded_df['Sellers'] = exploded_df['Sellers'].astype(str)
                exploded_df['Sellers'] = exploded_df['Sellers'].str.replace(r'[\n|;/،]', ',', regex=True)
                exploded_df['Sellers'] = exploded_df['Sellers'].str.split(',')
                exploded_df = exploded_df.explode('Sellers')
                exploded_df['Sellers'] = exploded_df['Sellers'].str.strip()
                exploded_df = exploded_df[exploded_df['Sellers'] != ""]
                exploded_df = exploded_df[exploded_df['Sellers'].str.lower() != "nan"]
                
                # --- CREATE SUMMARY DATA (UPDATED LOGIC) ---
                # Ensure math columns are numeric
                for col in ['SOH_Total', 'Replenishment Qty']:
                    exploded_df[col] = pd.to_numeric(exploded_df[col], errors='coerce').fillna(0)
                
                # Decide how to group based on user selection
                groupby_cols = ['Sellers', 'Category'] if selected_category == "All Categories" else ['Sellers']
                
                # 1. Base Summary (SKUs, SOH, Replenishment)
                base_summary = exploded_df.groupby(groupby_cols).agg(
                    Total_SKUs=('sku', 'count'),
                    Total_SOH=('SOH_Total', 'sum'),
                    Total_Replenishment=('Replenishment Qty', 'sum')
                ).reset_index()
                
                # 2. Live Flag Breakdown (Pivot Table)
                live_flag_summary = pd.pivot_table(
                    exploded_df,
                    index=groupby_cols,
                    columns='Live_flag',
                    values='sku',
                    aggfunc='count',
                    fill_value=0
                ).reset_index()
                
                # Remove the generic column index name to keep headers clean
                live_flag_summary.columns.name = None
                
                # 3. Merge them together into one master summary table
                summary_df = pd.merge(base_summary, live_flag_summary, on=groupby_cols, how='left')
                
                # --- OUTPUT GENERATION ---
                
                # OPTION 1: SUMMARY ONLY
                if output_type == "Summary Only (Single Excel File)":
                    excel_buffer = io.BytesIO()
                    summary_df.to_excel(excel_buffer, index=False, sheet_name="Summary")
                    
                    st.success("Summary generated successfully!")
                    st.download_button(
                        label="📥 Download Summary File",
                        data=excel_buffer.getvalue(),
                        file_name=f"{safe_category}_Summary_{current_date}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
                # OPTION 2: FULL PROCESSING (ZIP FOLDER)
                else:
                    zip_buffer = io.BytesIO()
                    
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        
                        # 1. Master File (Data + Summary Tabs)
                        master_file_name = f"{safe_category} Master {current_date}.xlsx"
                        master_buffer = io.BytesIO() 
                        
                        with pd.ExcelWriter(master_buffer, engine='xlsxwriter') as writer:
                            exploded_df[OUTPUT_COLS_ALL].to_excel(writer, index=False, sheet_name='Master Data')
                            summary_df.to_excel(writer, index=False, sheet_name='Summary')
                            
                        zip_file.writestr(f"{folder_name}/{master_file_name}", master_buffer.getvalue())
                        
                        # 2. Individual Seller Sheets
                        unique_sellers = exploded_df['Sellers'].unique()
                        
                        for seller in unique_sellers:
                            seller_df = exploded_df[exploded_df['Sellers'] == seller]
                            safe_seller = clean_filename(seller)
                            
                            seller_file_name = f"{safe_seller} replenishment_{current_date}.xlsx"
                            seller_buffer = io.BytesIO()
                            
                            seller_df[OUTPUT_COLS_SELLER].to_excel(seller_buffer, index=False)
                            zip_file.writestr(f"{folder_name}/{seller_file_name}", seller_buffer.getvalue())
                    
                    st.success("Full folder generated! Click below to download your ZIP file.")
                    st.download_button(
                        label="📥 Download ZIP Folder",
                        data=zip_buffer.getvalue(),
                        file_name=f"{folder_name}.zip",
                        mime="application/zip"
                    )
