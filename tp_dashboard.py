import streamlit as st
import pandas as pd
import os
import json
from typing import List

st.set_page_config(page_title="TP Worldwide Dashboard", layout="wide")
st.title("Transfer Pricing Worldwide Data Dashboard")

st.caption("Verbeterde versie met uitgebreide filters, kolom selectie & zoekfunctie.")

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

############################################
# Sidebar: Filters & Opties
############################################
st.sidebar.header("Filters")

# 1. Land selectie (nu standaard ALLES geselecteerd)
landen: List[str] = sorted(df['Country'].dropna().unique())
selectie_landen = st.sidebar.multiselect(
    "Landen", landen, default=landen, help="Standaard alle landen geselecteerd"
)

# 2. Snelle tekst zoekfilter (case-insensitive over alle string kolommen)
zoekterm = st.sidebar.text_input("Zoekterm (vrije tekst)", placeholder="bv. APA, OECD, Master file")

# 3. Vooraf gedefinieerde ja/nee kolommen (als aanwezig)
yn_kandidaten = [
    'DomesticTPObligations', 'OECDorBEPS', 'OECDGuidelines', 'APAAvailable',
    'BEPS13PenaltyProtection', 'MCAA_CbC', 'LocalFile', 'MasterFile'
]
actieve_yn = []
with st.sidebar.expander("Ja/Nee filters"):
    for col in yn_kandidaten:
        if col in df.columns:
            opties = sorted([x for x in df[col].dropna().unique() if str(x).strip() != ''])
            if opties:
                keuze = st.multiselect(col, opties, default=opties if len(opties) <= 6 else opties)  # default alle
                actieve_yn.append((col, keuze))

# 4. Dynamische categorische kolommen (kleine cardinaliteit, ex. <= 20, excl reeds opgenomen + Country)
with st.sidebar.expander("Extra categorische filters"):
    cat_filters = []
    for col in df.select_dtypes(include=['object']).columns:
        if col in ['Country'] + yn_kandidaten:
            continue
        unq = df[col].dropna().unique()
        if 1 < len(unq) <= 20:  # redelijke set
            values = sorted([x for x in unq if str(x).strip() != ''])
            gekozen = st.multiselect(col, values, default=values)
            cat_filters.append((col, gekozen))

# 5. Kolom selectie
with st.sidebar.expander("Kolommen zichtbaar"):
    alle_kolommen = list(df.columns)
    zichtbare_kolommen = st.multiselect("Selecteer kolommen", alle_kolommen, default=alle_kolommen)

# 6. Reset knop (herladen pagina)
if st.sidebar.button("Reset alle filters"):
    st.experimental_rerun()

############################################
# Filtering logic
############################################
gefilterd = df.copy()

# Landen filter
if selectie_landen:
    gefilterd = gefilterd[gefilterd['Country'].isin(selectie_landen)]

# Tekst zoekterm
if zoekterm:
    term = zoekterm.lower()
    string_cols = gefilterd.select_dtypes(include=['object']).columns
    mask = pd.Series(False, index=gefilterd.index)
    for c in string_cols:
        mask = mask | gefilterd[c].fillna('').str.lower().str.contains(term)
    gefilterd = gefilterd[mask]

# Ja/Nee filters
for col, keuzes in actieve_yn:
    if keuzes:
        gefilterd = gefilterd[gefilterd[col].isin(keuzes)]

# Extra categorische filters
for col, keuzes in cat_filters:
    if keuzes:
        gefilterd = gefilterd[gefilterd[col].isin(keuzes)]

# Kolom subset
if zichtbare_kolommen:
    gefilterd = gefilterd[zichtbare_kolommen]

############################################
# KPI sectie (bovenaan)
############################################
col1, col2, col3, col4 = st.columns(4)
col1.metric("Landen (totaal filtreerbaar)", df['Country'].nunique())
col2.metric("Records selectie", len(gefilterd))
if 'APAAvailable' in df.columns:
    pct_apa = (gefilterd.get('APAAvailable', pd.Series(dtype=str)).fillna('').str.contains('Yes', case=False)).mean()*100
    col3.metric("% APA (selectie)", f"{pct_apa:.0f}%")
else:
    col3.metric("% APA (selectie)", "n/a")
if 'OECDorBEPS' in df.columns:
    pct_beps = (gefilterd.get('OECDorBEPS', pd.Series(dtype=str)).fillna('').str.contains('Yes', case=False)).mean()*100
    col4.metric("% OECD/BEPS (selectie)", f"{pct_beps:.0f}%")
else:
    col4.metric("% OECD/BEPS (selectie)", "n/a")

############################################
# Tabs voor data & aanvullende views
############################################
tab_tabel, tab_deadlines, tab_info = st.tabs(["📊 Data", "⏱ Deadlines", "ℹ️ Info"])

def style_yes_no(val):
    v = str(val).strip().lower()
    if v == 'yes':
        return 'background-color: #d1f5d3; color:#065f08;'
    if v == 'no':
        return 'background-color: #f9d6d6; color:#7a0000;'
    return ''

with tab_tabel:
    st.subheader("Gefilterde data")
    if gefilterd.empty:
        st.warning("Geen resultaten voor de huidige filters")
    else:
        # Styling toepassen op object kolommen
        object_cols = gefilterd.select_dtypes(include=['object']).columns
        styled = gefilterd.style.applymap(style_yes_no, subset=object_cols)
        st.dataframe(styled, use_container_width=True, height=520)
        st.download_button(
            "Download selectie (CSV)",
            gefilterd.to_csv(index=False).encode('utf-8-sig'),
            file_name="tp_selection.csv",
            mime="text/csv",
            help="Exporteer de huidige gefilterde dataset"
        )

with tab_deadlines:
    st.subheader("Deadline kolommen")
    possible_cols = [c for c in df.columns if 'Deadline' in c]
    if possible_cols and not gefilterd.empty:
        deadline_df = df[df['Country'].isin(selectie_landen)] if selectie_landen else df
        deadline_df = deadline_df[['Country'] + possible_cols]
        st.dataframe(deadline_df, use_container_width=True, height=520)
    else:
        st.caption("Geen deadline kolommen of geen resultaten.")

with tab_info:
    st.markdown("""
    ### Uitleg & Tips
    - Gebruik de filters links om dataset te verfijnen.
    - Vrije tekst zoekt in alle tekst kolommen (case-insensitive).
    - 'Ja/Nee filters' tonen alleen kolommen die in het bronbestand voorkomen.
    - Via 'Kolommen zichtbaar' kun je kolommen snel aan/uit zetten voor de tabel.
    - Reset knop herlaadt de app naar de standaard (alle landen).
    - Download knop exporteert enkel de huidige selectie, niet de volledige dataset.
    
    Voeg eenvoudig extra visualisaties toe door onder de tabs extra secties toe te voegen.
    """)

st.markdown("""---\n*Klaar voor verdere uitbreiding: grafieken, pivot analyses, heatmaps enz.*""")
