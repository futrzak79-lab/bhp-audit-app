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
    
    # Zmień nazwy kolumn
    rename_map = {}
    for col in df.columns:
        col_lower = col.lower()
        if col_lower in ["lp", "l.p"]:
            rename_map[col] = "Lp"
        elif col_lower == "obszar":
            rename_map[col] = "Obszar"
        elif col_lower == "pytanie":
            rename_map[col] = "Pytanie"
        elif "podstawa" in col_lower:
            rename_map[col] = "Podstawa prawna"
        elif col_lower == "tak":
            rename_map[col] = "Tak"
        elif col_lower in ["n/d", "nd"]:
            rename_map[col] = "Nie dotyczy"
        elif col_lower == "nie":
            rename_map[col] = "Nie"
        elif col_lower in ["obserwacje", "uwagi"]:
            rename_map[col] = "Obserwacje uwagi"
    
    df = df.rename(columns=rename_map)
    
    # Dodaj kolumnę Ocena
    def get_ocena(row):
        tak_val = str(row.get("Tak", "")).lower().strip() if pd.notna(row.get("Tak")) else ""
        nie_val = str(row.get("Nie", "")).lower().strip() if pd.notna(row.get("Nie")) else ""
        nd_val = str(row.get("Nie dotyczy", "")).lower().strip() if pd.notna(row.get("Nie dotyczy")) else ""
        
        if tak_val in ["x", "tak", "1"]:
            return "TAK"
        if nie_val in ["x", "nie", "1"]:
            return "NIE"
        if nd_val in ["x", "n/d", "nd", "1"]:
            return "Nie dotyczy"
        return ""
    
    df["Ocena"] = df.apply(get_ocena, axis=1)
    
    # Wczytaj Akty prawne
    df_akty = pd.read_excel("wymagania_bhp.xlsx", sheet_name="Akty prawne")
    df_akty.columns = df_akty.iloc[0].astype(str).str.strip()
    df_akty = df_akty.iloc[1:].reset_index(drop=True)
    
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
    df_filt = df[df["Obszar"] == wybrany_obszar].copy()
else:
    df_filt = df.copy()

if tylko_niezgodne:
    df_filt = df_filt[df_filt["Ocena"] == "NIE"].copy()

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
    
    # Przygotuj dane do edycji
    df_edit = df_filt[["Lp", "Obszar", "Pytanie", "Podstawa prawna", "Ocena", "Obserwacje uwagi"]].copy()
    
    # Konfiguracja kolumn
    column_config = {
        "Ocena": st.column_config.SelectboxColumn(
            "Ocena",
            options=["", "TAK", "NIE", "Częściowo", "Nie dotyczy"],
            required=False,
        ),
        "Obserwacje uwagi": st.column_config.TextColumn("Uwagi", width="medium"),
        "Pytanie": st.column_config.TextColumn("Pytanie", width="large"),
    }
    
    # Jeśli mamy listę aktów, dodajemy selectbox dla podstawy prawnej
    if akty_lista:
        column_config["Podstawa prawna"] = st.column_config.SelectboxColumn(
            "Podstawa prawna",
            options=[""] + akty_lista,
            required=False,
        )
    
    # Edytowalna tabela
    edited_df = st.data_editor(
        df_edit,
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic"
    )
    
    # Przycisk zapisu
    if st.button("💾 Zapisz zmiany", use_container_width=True):
        # Zaktualizuj oryginalne dane
        for idx, row in edited_df.iterrows():
            mask = df["Lp"] == row["Lp"]
            df.loc[mask, "Ocena"] = row["Ocena"]
            df.loc[mask, "Obserwacje uwagi"] = row["Obserwacje uwagi"]
            df.loc[mask, "Podstawa prawna"] = row["Podstawa prawna"]
            
            # Aktualizuj kolumny Tak/Nie/Nie dotyczy
            ocena = row["Ocena"]
            if "Tak" in df.columns:
                df.loc[mask, "Tak"] = "x" if ocena == "TAK" else ""
            if "Nie" in df.columns:
                df.loc[mask, "Nie"] = "x" if ocena == "NIE" else ""
            if "Nie dotyczy" in df.columns:
                df.loc[mask, "Nie dotyczy"] = "n/d" if ocena == "Nie dotyczy" else ""
        
        save_checklist(df)
        st.success("✅ Zapisano!")
        st.rerun()
    
    # Wyświetl linki do aktów prawnych (jeśli istnieją)
    if akty_linki:
        st.markdown("---")
        st.subheader("🔗 Dostępne linki do aktów prawnych")
        for nazwa, link in akty_linki.items():
            st.markdown(f"- **{nazwa}**: [Zobacz na ISAP]({link})")

# ==================== TAB 2: AKTY PRAWNE ====================
with tab2:
    st.header("⚖️ Akty prawne")
    
    if df_akty is not None and not df_akty.empty:
        st.dataframe(df_akty, use_container_width=True)
        
        # Dodawanie nowego aktu
        with st.expander("➕ Dodaj nowy akt prawny"):
            col1, col2 = st.columns(2)
            with col1:
                nowy_akt = st.text_input("Nazwa aktu")
            with col2:
                nowy_link = st.text_input("Link do ISAP")
            
            if st.button("Dodaj") and nowy_akt:
                nowy_wiersz = pd.DataFrame({"Akt prawny": [nowy_akt], "Link": [nowy_link]})
                df_akty_new = pd.concat([df_akty, nowy_wiersz], ignore_index=True)
                with pd.ExcelWriter("wymagania_bhp.xlsx", engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                    df_akty_new.to_excel(writer, sheet_name="Akty prawne", index=False)
                st.success("✅ Dodano! Odśwież stronę.")
                st.rerun()
    else:
        st.warning("Brak arkusza 'Akty prawne'")

# ==================== TAB 3: RAPORT ====================
with tab3:
    st.header("📊 Raport zgodności BHP")
    
    df_oceny = df[df["Ocena"] != ""].copy()
    niezgodne = df_oceny[df_oceny["Ocena"] == "NIE"].copy()
    
    # Metryki
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
        cols_show = ["Lp", "Pytanie", "Obszar", "Obserwacje uwagi"]
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