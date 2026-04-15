import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import tempfile
import os
import base64
from datetime import datetime

st.set_page_config(page_title="BHP - Ocena zgodności", layout="wide")

# ==================== WCZYTYWANIE DANYCH ====================
def load_data():
    # Wczytaj Checklistę
    df = pd.read_excel("wymagania_bhp.xlsx", sheet_name="Checklista", header=None)
    
    # Znajdź wiersz z nagłówkami
    header_row = None
    for idx, row in df.iterrows():
        first_cell = str(row[0]).lower().strip() if pd.notna(row[0]) else ""
        if "lp" in first_cell:
            header_row = idx
            break
    
    if header_row is not None:
        df.columns = df.iloc[header_row].astype(str).str.strip()
        df = df.iloc[header_row + 1:].reset_index(drop=True)
    else:
        df.columns = df.iloc[0].astype(str).str.strip()
        df = df.iloc[1:].reset_index(drop=True)
    
    df = df.dropna(how='all')
    df.columns = df.columns.str.replace('.', '').str.strip()
    
    # Zmień nazwy kolumn na proste (bez spacji i znaków specjalnych)
    rename_map = {}
    for col in df.columns:
        col_lower = col.lower().strip()
        if col_lower in ["lp", "l.p"]:
            rename_map[col] = "Lp"
        elif col_lower == "obszar":
            rename_map[col] = "Obszar"
        elif col_lower == "pytanie":
            rename_map[col] = "Pytanie"
        elif "podstawa" in col_lower:
            rename_map[col] = "Podstawa_prawna"
        elif col_lower == "tak":
            rename_map[col] = "Tak"
        elif col_lower in ["n/d", "nd"]:
            rename_map[col] = "Nie_dotyczy"
        elif col_lower == "nie":
            rename_map[col] = "Nie"
        elif col_lower in ["obserwacje", "uwagi"]:
            rename_map[col] = "Uwagi"
    
    df = df.rename(columns=rename_map)
    
    # Uzupełnij brakujące kolumny
    for col in ["Lp", "Obszar", "Pytanie", "Podstawa_prawna", "Tak", "Nie", "Nie_dotyczy", "Uwagi"]:
        if col not in df.columns:
            df[col] = ""
    
    # Dodaj kolumnę Ocena
    def get_ocena(row):
        tak_val = str(row.get("Tak", "")).lower().strip() if pd.notna(row.get("Tak")) else ""
        nie_val = str(row.get("Nie", "")).lower().strip() if pd.notna(row.get("Nie")) else ""
        nd_val = str(row.get("Nie_dotyczy", "")).lower().strip() if pd.notna(row.get("Nie_dotyczy")) else ""
        
        if tak_val in ["x", "tak", "1"]:
            return "TAK"
        if nie_val in ["x", "nie", "1"]:
            return "NIE"
        if nd_val in ["x", "n/d", "nd", "1"]:
            return "Nie dotyczy"
        return ""
    
    df["Ocena"] = df.apply(get_ocena, axis=1)
    
    # Wczytaj Akty prawne
    df_akty = None
    try:
        df_akty = pd.read_excel("wymagania_bhp.xlsx", sheet_name="Akty prawne")
        df_akty.columns = df_akty.iloc[0].astype(str).str.strip()
        df_akty = df_akty.iloc[1:].reset_index(drop=True)
        
        akty_rename = {}
        for col in df_akty.columns:
            col_lower = col.lower()
            if "lp" in col_lower:
                akty_rename[col] = "Lp"
            elif "prawny" in col_lower or "akt" in col_lower:
                akty_rename[col] = "Akt_prawny"
            elif "link" in col_lower or "omawiane" in col_lower:
                akty_rename[col] = "Link"
        df_akty = df_akty.rename(columns=akty_rename)
    except:
        pass
    
    return df, df_akty

def save_checklist(df):
    # Zapisz tylko oryginalne kolumny (bez Ocena)
    cols_to_save = [c for c in df.columns if c not in ["Ocena"]]
    df_save = df[cols_to_save].copy()
    try:
        with pd.ExcelWriter("wymagania_bhp.xlsx", engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df_save.to_excel(writer, sheet_name="Checklista", index=False)
    except:
        with pd.ExcelWriter("wymagania_bhp.xlsx", engine="openpyxl", mode="w") as writer:
            df_save.to_excel(writer, sheet_name="Checklista", index=False)

df, df_akty = load_data()

# ==================== PRZYGOTOWANIE LISTY AKTÓW PRAWNYCH ====================
akty_lista = []
akty_linki = {}

if df_akty is not None and not df_akty.empty:
    if "Akt_prawny" in df_akty.columns:
        akty_lista = df_akty["Akt_prawny"].dropna().astype(str).tolist()
    if "Link" in df_akty.columns:
        for _, row in df_akty.iterrows():
            nazwa = str(row["Akt_prawny"]) if pd.notna(row.get("Akt_prawny")) else ""
            link = str(row["Link"]) if pd.notna(row.get("Link")) else ""
            if nazwa and link.startswith("http"):
                akty_linki[nazwa] = link

# ==================== SIDEBAR ====================
st.sidebar.header("⚙️ Panel sterowania")

obszary_lista = df["Obszar"].dropna().unique().tolist()
if obszary_lista:
    obszary = ["Wszystkie"] + sorted(obszary_lista)
    wybrany_obszar = st.sidebar.selectbox("Obszar BHP", obszary)
else:
    wybrany_obszar = "Wszystkie"

tylko_niezgodne = st.sidebar.toggle("🔴 Pokaż tylko niezgodne")

if wybrany_obszar != "Wszystkie":
    df_filt = df[df["Obszar"] == wybrany_obszar].copy()
else:
    df_filt = df.copy()

if tylko_niezgodne:
    df_filt = df_filt[df_filt["Ocena"] == "NIE"].copy()

# Resetuj indeks
df_filt = df_filt.reset_index(drop=True)

# ==================== ZAKŁADKI ====================
tab0, tab1, tab2, tab3 = st.tabs(["📄 Strona tytułowa", "📋 Checklista", "⚖️ Akty prawne", "📊 Raport"])

# ==================== TAB 0: STRONA TYTUŁOWA ====================
with tab0:
    st.header("📄 Informacje o audycie")
    
    col1, col2 = st.columns(2)
    with col1:
        zaklad = st.text_input("🏭 **Zakład**", value="")
        data_audytu = st.date_input("📅 **Data**", value=datetime.now().date())
    with col2:
        imie_nazwisko = st.text_input("👤 **Oceniający**", value="")
        stanowisko = st.text_input("📌 **Stanowisko**", value="")

# ==================== TAB 1: CHECKLISTA ====================
with tab1:
    st.header("📋 Ocena zgodności wymagań BHP")
    
    # Pasek postępu
    ocenione = df_filt[df_filt["Ocena"] != ""].shape[0]
    wszystkie = len(df_filt)
    if wszystkie > 0:
        st.progress(ocenione / wszystkie, text=f"✅ Postęp: {ocenione}/{wszystkie}")
    
    st.markdown("---")
    
    # Przechowuj zmiany w session state
    if "changes" not in st.session_state:
        st.session_state.changes = {}
    
    # Wyświetl każde pytanie
    for i, row in df_filt.iterrows():
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"**{row.get('Lp', i+1)}. {row.get('Pytanie', '')}**")
                st.caption(f"Obszar: {row.get('Obszar', '')}")
            
            with col2:
                # Podstawa prawna - selectbox
                current_podstawa = str(row.get("Podstawa_prawna", "")) if pd.notna(row.get("Podstawa_prawna")) else ""
                
                if akty_lista:
                    options = [""] + akty_lista
                    idx_val = 0
                    if current_podstawa in akty_lista:
                        idx_val = akty_lista.index(current_podstawa) + 1
                    
                    new_podstawa = st.selectbox(
                        "Podstawa prawna",
                        options,
                        index=idx_val,
                        key=f"podstawa_{i}"
                    )
                    
                    if new_podstawa != current_podstawa:
                        st.session_state.changes[f"podstawa_{i}"] = new_podstawa
                    
                    # Pokaż link jeśli istnieje
                    if new_podstawa and new_podstawa in akty_linki:
                        st.markdown(f"[🔗 Zobacz akt]({akty_linki[new_podstawa]})")
                else:
                    st.text(current_podstawa if current_podstawa else "-")
            
            with col3:
                # Ocena - selectbox
                current_ocena = str(row.get("Ocena", "")) if pd.notna(row.get("Ocena")) else ""
                ocena_options = ["", "TAK", "NIE", "Częściowo", "Nie dotyczy"]
                ocena_idx = ocena_options.index(current_ocena) if current_ocena in ocena_options else 0
                
                new_ocena = st.selectbox(
                    "Ocena",
                    ocena_options,
                    index=ocena_idx,
                    key=f"ocena_{i}"
                )
                
                if new_ocena != current_ocena:
                    st.session_state.changes[f"ocena_{i}"] = new_ocena
            
            # Uwagi
            current_uwagi = str(row.get("Uwagi", "")) if pd.notna(row.get("Uwagi")) else ""
            new_uwagi = st.text_area("Uwagi", value=current_uwagi, key=f"uwagi_{i}", height=50)
            
            if new_uwagi != current_uwagi:
                st.session_state.changes[f"uwagi_{i}"] = new_uwagi
    
    # Przycisk zapisu
    if st.button("💾 Zapisz wszystkie zmiany", use_container_width=True):
        for key, value in st.session_state.changes.items():
            parts = key.split("_")
            idx = int(parts[1])
            typ = parts[0]
            
            if typ == "podstawa":
                df_filt.loc[idx, "Podstawa_prawna"] = value
                # Znajdź w oryginalnym df
                mask = df["Lp"] == df_filt.loc[idx, "Lp"]
                df.loc[mask, "Podstawa_prawna"] = value
            elif typ == "ocena":
                df_filt.loc[idx, "Ocena"] = value
                mask = df["Lp"] == df_filt.loc[idx, "Lp"]
                df.loc[mask, "Ocena"] = value
                # Aktualizuj kolumny Tak/Nie/Nie_dotyczy
                if "Tak" in df.columns:
                    df.loc[mask, "Tak"] = "x" if value == "TAK" else ""
                if "Nie" in df.columns:
                    df.loc[mask, "Nie"] = "x" if value == "NIE" else ""
                if "Nie_dotyczy" in df.columns:
                    df.loc[mask, "Nie_dotyczy"] = "n/d" if value == "Nie dotyczy" else ""
            elif typ == "uwagi":
                df_filt.loc[idx, "Uwagi"] = value
                mask = df["Lp"] == df_filt.loc[idx, "Lp"]
                df.loc[mask, "Uwagi"] = value
        
        save_checklist(df)
        st.session_state.changes = {}
        st.success("✅ Zapisano!")
        st.rerun()

# ==================== TAB 2: AKTY PRAWNE ====================
with tab2:
    st.header("⚖️ Akty prawne")
    
    if df_akty is not None and not df_akty.empty:
        st.dataframe(df_akty, use_container_width=True)
        
        with st.expander("➕ Dodaj nowy akt prawny"):
            col1, col2 = st.columns(2)
            with col1:
                nowy_akt = st.text_input("Nazwa aktu")
            with col2:
                nowy_link = st.text_input("Link do ISAP")
            
            if st.button("Dodaj") and nowy_akt:
                nowy_wiersz = pd.DataFrame({"Akt_prawny": [nowy_akt], "Link": [nowy_link]})
                df_akty_new = pd.concat([df_akty, nowy_wiersz], ignore_index=True)
                with pd.ExcelWriter("wymagania_bhp.xlsx", engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                    df_akty_new.to_excel(writer, sheet_name="Akty prawne", index=False)
                st.success("✅ Dodano! Odśwież stronę.")
                st.rerun()
    else:
        st.info("Brak arkusza 'Akty prawne'")

# ==================== TAB 3: RAPORT ====================
with tab3:
    st.header("📊 Raport zgodności BHP")
    
    df_oceny = df[df["Ocena"] != ""].copy()
    niezgodne = df_oceny[df_oceny["Ocena"] == "NIE"].copy()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Wszystkie wymagania", len(df_oceny))
    with col2:
        st.metric("Zgodne (TAK)", len(df_oceny[df_oceny["Ocena"] == "TAK"]))
    with col3:
        st.metric("Niezgodności (NIE)", len(niezgodne))
    with col4:
        zgodnosc = len(df_oceny[df_oceny["Ocena"] == "TAK"]) / len(df_oceny) * 100 if len(df_oceny) > 0 else 0
        st.metric("Poziom zgodności", f"{zgodnosc:.1f}%")
    
    # Wykres
    fig, ax = plt.subplots()
    oceny_counts = df_oceny["Ocena"].value_counts()
    if not oceny_counts.empty:
        ax.pie(oceny_counts, labels=oceny_counts.index, autopct="%1.1f%%")
        ax.set_title("Ogólna zgodność")
        st.pyplot(fig)
    
    # Lista niezgodności
    st.subheader("📋 Lista niezgodności")
    if not niezgodne.empty:
        cols_show = ["Lp", "Pytanie", "Obszar", "Uwagi"]
        cols_exist = [c for c in cols_show if c in niezgodne.columns]
        st.dataframe(niezgodne[cols_exist], use_container_width=True)
    else:
        st.success("🎉 Brak niezgodności!")
    
    # PDF
    if st.button("📄 Generuj raport PDF"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(200, 10, txt="Raport oceny zgodności BHP", ln=1, align="C")
        pdf.set_font("Arial", size=10)
        pdf.cell(200, 10, txt=f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=1, align="C")
        pdf.ln(10)
        
        pdf.set_font("Arial", "B", 12)
        pdf.cell(200, 10, txt="Podsumowanie", ln=1)
        pdf.set_font("Arial", size=10)
        pdf.cell(200, 8, txt=f"Zgodnych: {len(df_oceny[df_oceny['Ocena']=='TAK'])}", ln=1)
        pdf.cell(200, 8, txt=f"Niezgodności: {len(niezgodne)}", ln=1)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdf.output(tmp.name)
            with open(tmp.name, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            st.markdown(f'<a href="data:application/octet-stream;base64,{b64}" download="raport.pdf">📥 Pobierz PDF</a>', unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.caption(f"© BHP Audyt | {len(df)} wymagań")