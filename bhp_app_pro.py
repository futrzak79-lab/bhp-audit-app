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
    # Wczytaj Checklistę – pomiń pierwsze puste wiersze i użyj pierwszego wiersza z danymi jako nagłówki
    df = pd.read_excel("wymagania_bhp.xlsx", sheet_name="Checklista", header=None)
    
    # Znajdź pierwszy wiersz, który zawiera "lp." lub "Lp" (to będą nagłówki)
    header_row = None
    for idx, row in df.iterrows():
        first_cell = str(row[0]).lower().strip() if pd.notna(row[0]) else ""
        if "lp" in first_cell or first_cell == "lp.":
            header_row = idx
            break
    
    if header_row is not None:
        # Ustaw nagłówki z tego wiersza
        df.columns = df.iloc[header_row].astype(str).str.strip()
        # Pomiń wiersze do nagłówka włącznie
        df = df.iloc[header_row + 1:].reset_index(drop=True)
    else:
        # Jeśli nie znaleziono, załóż że pierwszy wiersz to nagłówki
        df.columns = df.iloc[0].astype(str).str.strip()
        df = df.iloc[1:].reset_index(drop=True)
    
    # Usuń całkowicie puste wiersze
    df = df.dropna(how='all')
    
    # Wyczyść nazwy kolumn (usuń spacje, kropki)
    df.columns = df.columns.str.replace('.', '').str.strip()
    
    # Zmień nazwy kolumn na standardowe
    rename_map = {}
    for col in df.columns:
        col_lower = col.lower()
        if col_lower in ["lp", "lp", "l.p"]:
            rename_map[col] = "Lp"
        elif col_lower in ["obszar"]:
            rename_map[col] = "Obszar"
        elif col_lower in ["pytanie"]:
            rename_map[col] = "Pytanie"
        elif "podstawa" in col_lower:
            rename_map[col] = "Podstawa prawna"
        elif col_lower in ["tak"]:
            rename_map[col] = "Tak"
        elif col_lower in ["n/d", "nd"]:
            rename_map[col] = "Nie dotyczy"
        elif col_lower in ["nie"]:
            rename_map[col] = "Nie"
        elif col_lower in ["obserwacje", "uwagi"]:
            rename_map[col] = "Obserwacje uwagi"
    
    df = df.rename(columns=rename_map)
    
    # Dodaj kolumnę Ocena
    def get_ocena(row):
        if "Tak" in row and str(row["Tak"]).lower() in ["x", "tak", "1", "true", "yes"]:
            return "TAK"
        if "Nie" in row and str(row["Nie"]).lower() in ["x", "nie", "1", "false", "no"]:
            return "NIE"
        if "Nie dotyczy" in row and str(row["Nie dotyczy"]).lower() in ["x", "n/d", "nd", "1"]:
            return "Nie dotyczy"
        return ""
    
    if "Tak" in df.columns and "Nie" in df.columns:
        df["Ocena"] = df.apply(get_ocena, axis=1)
    else:
        df["Ocena"] = ""
    
    # Wczytaj Akty prawne
    df_akty = pd.read_excel("wymagania_bhp.xlsx", sheet_name="Akty prawne")
    df_akty.columns = df_akty.iloc[0].astype(str).str.strip()
    df_akty = df_akty.iloc[1:].reset_index(drop=True)
    
    # Zmień nazwy kolumn w aktach prawnych
    akty_rename = {}
    for col in df_akty.columns:
        col_lower = col.lower()
        if "lp" in col_lower:
            akty_rename[col] = "Lp"
        elif "prawny" in col_lower or "akt" in col_lower:
            akty_rename[col] = "Akt prawny"
        elif "link" in col_lower or "omawiane" in col_lower:
            akty_rename[col] = "Link"
    df_akty = df_akty.rename(columns=akty_rename)
    
    return df, df_akty

def save_checklist(df):
    # Zachowaj tylko oryginalne kolumny
    cols_to_save = [c for c in df.columns if c not in ["Ocena"]]
    df_save = df[cols_to_save].copy()
    with pd.ExcelWriter("wymagania_bhp.xlsx", engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        df_save.to_excel(writer, sheet_name="Checklista", index=False)

df, df_akty = load_data()

# ==================== PRZYGOTOWANIE LISTY AKTÓW PRAWNYCH ====================
akty_lista = []
akty_linki = {}

if df_akty is not None and not df_akty.empty:
    if "Akt prawny" in df_akty.columns:
        akty_lista = df_akty["Akt prawny"].dropna().astype(str).tolist()
    if "Link" in df_akty.columns:
        for _, row in df_akty.iterrows():
            nazwa = str(row["Akt prawny"]) if pd.notna(row.get("Akt prawny")) else ""
            link = str(row["Link"]) if pd.notna(row.get("Link")) else ""
            if nazwa and link.startswith("http"):
                akty_linki[nazwa] = link

# ==================== SIDEBAR ====================
st.sidebar.header("⚙️ Panel sterowania")

if "Obszar" in df.columns and df["Obszar"].notna().any():
    obszary = ["Wszystkie"] + sorted(df["Obszar"].dropna().unique().tolist())
    wybrany_obszar = st.sidebar.selectbox("Obszar BHP", obszary)
else:
    wybrany_obszar = "Wszystkie"

tylko_niezgodne = st.sidebar.toggle("🔴 Pokaż tylko niezgodne (NIE)")

if wybrany_obszar != "Wszystkie":
    df_filt = df[df["Obszar"] == wybrany_obszar]
else:
    df_filt = df.copy()

if tylko_niezgodne:
    df_filt = df_filt[df_filt["Ocena"] == "NIE"]

# ==================== ZAKŁADKI ====================
tab0, tab1, tab2, tab3 = st.tabs(["📄 Strona tytułowa", "📋 Checklista", "⚖️ Akty prawne", "📊 Raport"])

# ==================== TAB 0: STRONA TYTUŁOWA ====================
with tab0:
    st.header("📄 Informacje o audycie")
    
    col1, col2 = st.columns(2)
    with col1:
        zaklad = st.text_input("🏭 **Zakład**", value="", placeholder="Wpisz nazwę zakładu pracy")
        data_audytu = st.date_input("📅 **Data**", value=datetime.now().date())
    with col2:
        imie_nazwisko = st.text_input("👤 **Oceniający (imię i nazwisko)**", value="")
        stanowisko = st.text_input("📌 **Stanowisko**", value="")

# ==================== TAB 1: CHECKLISTA ====================
with tab1:
    st.header("📋 Ocena zgodności wymagań BHP")
    
    ocenione = df_filt[df_filt["Ocena"] != ""].shape[0]
    wszystkie = df_filt.shape[0]
    if wszystkie > 0:
        progress = ocenione / wszystkie
        st.progress(progress, text=f"✅ Postęp: {int(progress*100)}% ({ocenione}/{wszystkie})")
    
    st.markdown("---")
    
    for idx, row in df_filt.iterrows():
        with st.container():
            cols = st.columns([0.5, 1.5, 2.5, 2, 1, 1.5])
            
            cols[0].markdown(f"**{row['Lp']}**")
            cols[1].write(row.get("Obszar", ""))
            cols[2].write(row.get("Pytanie", ""))
            
            # Podstawa prawna
            current_value = row.get("Podstawa prawna", "")
            if pd.isna(current_value):
                current_value = ""
            
            if akty_lista:
                options = [""] + akty_lista
                current_index = 0
                if current_value in akty_lista:
                    current_index = akty_lista.index(current_value) + 1
                
                selected = cols[3].selectbox("Podstawa", options, index=current_index, key=f"akt_{idx}")
                if selected != current_value:
                    df.at[idx, "Podstawa prawna"] = selected
                    save_checklist(df)
                    st.rerun()
                if selected and selected in akty_linki:
                    cols[3].markdown(f"[🔗 Link]({akty_linki[selected]})")
            else:
                cols[3].write(current_value)
            
            # Ocena
            ocena_opcje = ["", "TAK", "NIE", "Częściowo", "Nie dotyczy"]
            current_ocena = row.get("Ocena", "")
            ocena_idx = ocena_opcje.index(current_ocena) if current_ocena in ocena_opcje else 0
            new_ocena = cols[4].selectbox("Ocena", ocena_opcje, index=ocena_idx, key=f"ocena_{idx}")
            
            if new_ocena != current_ocena:
                df.at[idx, "Ocena"] = new_ocena
                if "Tak" in df.columns:
                    df.at[idx, "Tak"] = "x" if new_ocena == "TAK" else ""
                if "Nie" in df.columns:
                    df.at[idx, "Nie"] = "x" if new_ocena == "NIE" else ""
                if "Nie dotyczy" in df.columns:
                    df.at[idx, "Nie dotyczy"] = "n/d" if new_ocena == "Nie dotyczy" else ""
                save_checklist(df)
                st.rerun()
            
            # Komentarz
            current_kom = row.get("Obserwacje uwagi", "")
            new_kom = cols[5].text_area("Uwagi", value=current_kom, key=f"kom_{idx}", height=60, label_visibility="collapsed")
            if new_kom != current_kom:
                df.at[idx, "Obserwacje uwagi"] = new_kom
                save_checklist(df)
                st.rerun()
        
        st.divider()
    
    if st.button("💾 Zapisz wszystko", use_container_width=True):
        save_checklist(df)
        st.success("✅ Zapisano!")

# ==================== TAB 2: AKTY PRAWNE ====================
with tab2:
    st.header("⚖️ Akty prawne")
    if df_akty is not None and not df_akty.empty:
        st.dataframe(df_akty, use_container_width=True)

# ==================== TAB 3: RAPORT ====================
with tab3:
    st.header("📊 Raport")
    niezgodne = df[df["Ocena"] == "NIE"]
    st.metric("Liczba niezgodności", len(niezgodne))
    if not niezgodne.empty:
        st.dataframe(niezgodne[["Lp", "Pytanie", "Obszar"]])