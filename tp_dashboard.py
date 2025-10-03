import streamlit as st
import pandas as pd
import os
import json

st.set_page_config(page_title="TP Worldwide Dashboard", layout="wide")
st.title("Transfer Pricing Worldwide Data Dashboard")

DATA_CANDIDATES = [
    # Primary new target file names (first match wins)
    os.path.join(os.path.dirname(__file__), 'extracted_tp_data_v2_2.csv'),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'extracted_tp_data_v2_2.csv'),
    # Backwards compatibility fallbacks
    os.path.join(os.path.dirname(__file__), 'extracted_tp_data_v2.csv'),
    os.path.join(os.path.dirname(__file__), 'extracted_tp_data.csv'),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'extracted_tp_data_v2.csv'),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'extracted_tp_data.csv'),
]
JSONL_CANDIDATE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'extracted_data.jsonl')

EXPECTED_MIN_COLUMNS = ["Country", "TaxAuthority", "TPLaw", "TPStartDate"]

@st.cache_data(show_spinner=False)
def load_csv_first() -> pd.DataFrame:
    for p in DATA_CANDIDATES:
        if os.path.exists(p):
            try:
                df = pd.read_csv(p)
                st.sidebar.success(f"Loaded: {os.path.basename(p)}")
                return df
            except Exception as e:
                st.sidebar.warning(f"Kon {os.path.basename(p)} niet lezen: {e}")
    return pd.DataFrame()

@st.cache_data(show_spinner=False)
def load_jsonl_fallback() -> pd.DataFrame:
    if not os.path.exists(JSONL_CANDIDATE):
        return pd.DataFrame()
    rows = []
    with open(JSONL_CANDIDATE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)

df = load_csv_first()
if df.empty:
    st.info("CSV niet gevonden, probeer JSONL fallback te laden…")
    df = load_jsonl_fallback()

if df.empty:
    st.error("Geen data gevonden. Plaats 'extracted_tp_data_v2_2.csv' (of eerdere fallback bestandsnaam) of het state-bestand 'extracted_data.jsonl'.")
    st.stop()

# Basisvalidatie
missing_core = [c for c in EXPECTED_MIN_COLUMNS if c not in df.columns]
if missing_core:
    st.warning(f"Ontbrekende kernkolommen: {', '.join(missing_core)}")
else:
    st.caption("Alle kernkolommen aanwezig.")

# KPI's
col1, col2, col3, col4 = st.columns(4)
col1.metric("Landen", df['Country'].nunique())
col2.metric("Records", len(df))
if 'APAAvailable' in df.columns:
    pct_apa = (df['APAAvailable'].fillna('').str.contains('Yes', case=False)).mean()*100
    col3.metric("% APA beschikbaar", f"{pct_apa:.0f}%")
else:
    col3.metric("% APA beschikbaar", "n/a")
if 'OECDorBEPS' in df.columns:
    pct_beps = (df['OECDorBEPS'].fillna('').str.contains('Yes', case=False)).mean()*100
    col4.metric("% OECD/BEPS", f"{pct_beps:.0f}%")
else:
    col4.metric("% OECD/BEPS", "n/a")

# Filters
landen = sorted(df['Country'].dropna().unique())
selectie = st.multiselect("Selecteer land(en)", landen, default=landen[:1])
gefilterd = df[df['Country'].isin(selectie)] if selectie else df.iloc[0:0]

st.subheader("Data")
st.dataframe(gefilterd, use_container_width=True, height=500)

# Deadlines view
with st.expander("Deadlines (indien kolommen aanwezig)"):
    possible_cols = [c for c in df.columns if 'Deadline' in c]
    if possible_cols and not gefilterd.empty:
        st.write(gefilterd[['Country'] + possible_cols].head(100))
    else:
        st.caption("Geen deadline kolommen of geen selectie.")

# Download
st.download_button(
    "Download selectie (CSV)",
    gefilterd.to_csv(index=False).encode('utf-8-sig'),
    file_name="tp_selection.csv",
    mime="text/csv"
)

st.markdown("""
*Filter, analyseer en exporteer TP-data. Voeg eenvoudig extra grafieken toe.*
""")
