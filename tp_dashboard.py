import streamlit as st
import pandas as pd
import os
import json
from typing import List
import plotly.express as px

# --- PAGINA CONFIGURATIE ---
st.set_page_config(
    page_title="TP Compliance Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- AANGEPASTE STYLING ---
st.markdown("""
<style>
    /* Strakkere containers */
    [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
        border: 1px solid #e6e6e6;
        border-radius: 0.5rem;
        padding: 1rem 1rem 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
    }
    /* KPI Metrics */
    [data-testid="stMetric"] {
        background-color: #fafafa;
        border: 1px solid #e6e6e6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    .st-emotion-cache-1vzeuhh { /* Target de metric value */
        font-size: 2.5rem !important;
    }
</style>
""", unsafe_allow_html=True)


# --- DATA LADEN ---
@st.cache_data(show_spinner="Loading data...")
def load_data() -> pd.DataFrame:
    """Laadt data, met CSV als prioriteit en JSONL als fallback."""
    # Pad definities
    base_dir = os.path.dirname(os.path.dirname(__file__))
    csv_path = os.path.join(base_dir, 'extracted_core_tp_data.csv')
    jsonl_path = os.path.join(base_dir, 'extracted_data_core.jsonl')

    # 1. Probeer CSV
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            st.sidebar.success(f"Loaded: {os.path.basename(csv_path)}")
            return df
        except Exception as e:
            st.sidebar.warning(f"Could not read CSV: {e}")

    # 2. Fallback naar JSONL
    if os.path.exists(jsonl_path):
        st.sidebar.info("CSV not found, falling back to JSONL.")
        rows = []
        column_mapping = {
            "Any mandatory MF/LF filing?": "Any_mandatory_MF_LF_filing", "MF deadline": "MF_deadline",
            "MF filing req.?": "MF_filing_req", "MF threshold*": "MF_threshold", "LF deadline": "LF_deadline",
            "LF filing req.?": "LF_filing_req", "LF threshold*": "LF_threshold",
            "CbCr notification deadline": "CbCr_notification_deadline", "CbCr filing deadline": "CbCr_filing_deadline",
            "CbCr threshold": "CbCr_threshold", "Local TP reqs.": "Local_TP_reqs",
            "Local TP reqs. deadline": "Local_TP_reqs_deadline", "Other": "Other"
        }
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if rows:
            df = pd.DataFrame(rows).rename(columns=column_mapping)
            # Zorg dat alle kolommen uit de mapping bestaan
            for target_col in column_mapping.values():
                if target_col not in df.columns:
                    df[target_col] = "N/A"
            st.sidebar.success(f"Loaded: {os.path.basename(jsonl_path)}")
            return df

    return pd.DataFrame()

df = load_data()

if df.empty:
    st.error("❌ No data found. Please run the `extract_core_pdf.py` script first.")
    st.stop()

# --- SIDEBAR / FILTERS ---
with st.sidebar:
    st.title("🌍 TP Dashboard")
    st.markdown("---")
    st.header("Filters")

    landen = sorted(df['Country'].dropna().unique())
    selectie_landen = st.multiselect("Countries", landen, default=landen)

    zoekterm = st.text_input("Free text search", placeholder="e.g., Yes, 12 months, upon request")

    with st.expander("Detailed Filters", expanded=True):
        yn_cols = ['Any_mandatory_MF_LF_filing', 'MF_filing_req', 'LF_filing_req']
        actieve_yn = []
        for col in yn_cols:
            if col in df.columns:
                opties = sorted([x for x in df[col].dropna().unique() if str(x).strip()])
                if opties:
                    keuze = st.multiselect(col, opties, default=opties)
                    actieve_yn.append((col, keuze))

    with st.expander("Column Selection"):
        zichtbare_kolommen = st.multiselect("Show columns", list(df.columns), default=list(df.columns))

    if st.button("Reset Filters", use_container_width=True):
        st.experimental_rerun()

# --- FILTERING LOGIC ---
gefilterd = df.copy()
if selectie_landen:
    gefilterd = gefilterd[gefilterd['Country'].isin(selectie_landen)]
if zoekterm:
    term = zoekterm.lower()
    string_cols = gefilterd.select_dtypes(include=['object']).columns
    mask = gefilterd[string_cols].fillna('').apply(lambda col: col.str.lower().str.contains(term)).any(axis=1)
    gefilterd = gefilterd[mask]
for col, keuzes in actieve_yn:
    if keuzes:
        gefilterd = gefilterd[gefilterd[col].isin(keuzes)]

# --- HOOFDPAGINA ---
st.title("TP Compliance Overview")
st.markdown(f"Analysis of **{len(gefilterd)}** of **{len(df)}** countries.")

# --- KPI SECTIE ---
st.markdown("### Key Metrics")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Countries", df['Country'].nunique())
with col2:
    st.metric("Filtered Countries", gefilterd['Country'].nunique())
with col3:
    if not gefilterd.empty and 'Any_mandatory_MF_LF_filing' in gefilterd.columns:
        mandatory_pct = (gefilterd['Any_mandatory_MF_LF_filing'].str.contains('Yes', case=False, na=False)).mean() * 100
        st.metric("Mandatory Filing (selection)", f"{mandatory_pct:.0f}%")
    else:
        st.metric("Mandatory Filing", "N/A")

st.markdown("---")

# --- TABS ---
tab_data, tab_vis, tab_info = st.tabs(["📊 Data Overview", "📈 Visualizations", "ℹ️ Info"])

with tab_data:
    st.subheader("Detailed Data")
    if gefilterd.empty:
        st.warning("No results for the current filters.")
    else:
        # Definieer kolomconfiguratie voor betere weergave
        column_config = {
            "Country": st.column_config.TextColumn("Country", width="medium"),
            "Other": st.column_config.LinkColumn("Other Info", width="large"),
        }
        # Voeg styling toe voor ja/nee kolommen
        def style_yes_no(val):
            v = str(val).strip().lower()
            if 'yes' in v: return 'background-color: #e5f5e0; color:#34a853;'
            if 'no' in v: return 'background-color: #fce8e6; color:#ea4335;'
            return ''

        display_df = gefilterd[zichtbare_kolommen] if zichtbare_kolommen else gefilterd
        
        st.dataframe(
            display_df.style.applymap(style_yes_no, subset=[c for c in yn_cols if c in display_df.columns]),
            column_config=column_config,
            use_container_width=True,
            height=600
        )
        st.download_button(
            "📥 Download Selection (CSV)",
            gefilterd.to_csv(index=False).encode('utf-8-sig'),
            "tp_core_selection.csv", "text/csv", use_container_width=True
        )

with tab_vis:
    st.subheader("Visual Analysis")
    if gefilterd.empty:
        st.warning("Select data to display charts.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### Filing Requirement Distribution")
            # Grafiek voor MF/LF filing requirement
            filing_req_col = 'MF_filing_req'
            if filing_req_col in gefilterd.columns:
                counts = gefilterd[filing_req_col].value_counts().reset_index()
                counts.columns = [filing_req_col, 'Number of Countries']
                
                fig = px.pie(counts, names=filing_req_col, values='Number of Countries',
                             title='Master File Filing Requirements', hole=0.3,
                             color_discrete_map={'Yes': '#34a853', 'No': '#ea4335', 'No; submit upon request': '#fbbc05'})
                fig.update_layout(legend_title_text='Requirement')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption(f"Column '{filing_req_col}' not found.")

        with col2:
            st.markdown("##### Countries per Deadline Type")
            deadline_col = 'MF_deadline'
            if deadline_col in gefilterd.columns:
                deadline_counts = gefilterd[deadline_col].value_counts().nlargest(10).reset_index()
                deadline_counts.columns = ['Deadline', 'Number of Countries']
                
                fig2 = px.bar(deadline_counts, x='Number of Countries', y='Deadline', orientation='h',
                              title='Top 10 Master File Deadlines', text='Number of Countries')
                fig2.update_layout(yaxis={'categoryorder':'total ascending'})
                fig2.update_traces(marker_color='#4285f4', textposition='outside')
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.caption(f"Column '{deadline_col}' not found.")


with tab_info:
    st.subheader("About this Dashboard")
    st.markdown("""
    This dashboard is designed to provide a quick and effective overview of the "core" transfer pricing compliance data.

    **How to use:**
    - **Filters:** Use the options in the sidebar to refine the dataset. You can filter by country, search by keyword, or select specific yes/no answers.
    - **Data Overview:** The main table shows the filtered data. Columns with "Yes" or "No" are colored green or red for quick recognition.
    - **Visualizations:** The charts provide a visual summary of the selected data, such as the distribution of filing requirements.
    - **Download:** Use the download button below the table to export the current selection to a CSV file.

    *This dashboard is built with Streamlit and Plotly Express.*
    """)

st.markdown("---")
st.caption("Dashboard v2.0 - Developed for a clean and effective data presentation.")
