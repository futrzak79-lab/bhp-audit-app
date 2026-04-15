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
@st.cache_data
def load_data():
    xl = pd.ExcelFile("wymagania_bhp.xlsx")
    sheet_names = xl.sheet_names
    
    # Strona tytułowa
    df_tytul = None
    if "Strona tytułowa" in sheet_names:
        df_tytul = pd.read_excel(xl, sheet_name="Strona tytułowa")
    
    # Checklista
    df_checklista = pd.read_excel(xl, sheet_name="Checklista")
    df_checklista.columns = df_checklista.columns.str.strip()
    
    # Akty prawne - baza do wyboru
    df_akty = None
    if "Akty prawne" in sheet_names:
        df_akty = pd.read_excel(xl, sheet_name="Akty prawne")
        df_akty.columns = df_akty.columns.str.strip()
    
    return df_tytul, df_checklista, df_akty

def save_checklist(df):
    with pd.ExcelWriter("wymagania_bhp.xlsx", engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        df.to_excel(writer, sheet_name="Checklista", index=False)

df_tytul, df, df_akty = load_data()

# ==================== PRZYGOTOWANIE LISTY AKTÓW PRAWNYCH ====================
akty_lista = []  # lista nazw do wyboru
akty_linki = {}  # słownik: nazwa -> link

if df_akty is not None and not df_akty.empty:
    # Zakładamy, że pierwsza kolumna to nazwa aktu (fragment)
    pierwsza_kolumna = df_akty.columns[0]
    akty_lista = df_akty[pierwsza_kolumna].dropna().astype(str).tolist()
    
    # Jeśli jest druga kolumna, potraktuj ją jako link
    if len(df_akty.columns) > 1:
        for _, row in df_akty.iterrows():
            nazwa = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
            link = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
            if nazwa and link.startswith("http"):
                akty_linki[nazwa] = link

# Upewnij się, że kolumna podstawa prawna istnieje
if "podstawa prawna" not in df.columns:
    df["podstawa prawna"] = ""

# ==================== SIDEBAR ====================
st.sidebar.header("⚙️ Panel sterowania")

if "obszar" in df.columns and df["obszar"].notna().any():
    obszary = ["Wszystkie"] + sorted(df["obszar"].dropna().unique().tolist())
    wybrany_obszar = st.sidebar.selectbox("Obszar BHP", obszary)
else:
    wybrany_obszar = "Wszystkie"

tylko_niezgodne = st.sidebar.toggle("🔴 Pokaż tylko niezgodne")

if wybrany_obszar != "Wszystkie":
    df_filt = df[df["obszar"] == wybrany_obszar]
else:
    df_filt = df.copy()

if tylko_niezgodne:
    df_filt = df_filt[df_filt["Ocena"].isin(["NIE", "Częściowo"])]

# ==================== ZAKŁADKI ====================
tab0, tab1, tab2, tab3 = st.tabs(["📄 Strona tytułowa", "📋 Checklista", "⚖️ Baza aktów prawnych", "📊 Raport"])

# ==================== TAB 0: STRONA TYTUŁOWA ====================
with tab0:
    st.header("📄 Informacje o audycie")
    
    col1, col2 = st.columns(2)
    with col1:
        data_audytu = st.date_input("📅 Data audytu", value=datetime.now().date())
    with col2:
        zaklad_pracy = st.text_input("🏭 Nazwa zakładu / lokalizacja", value="")
    
    col3, col4 = st.columns(2)
    with col3:
        audytor = st.text_input("👤 Imię i nazwisko audytora", value="")
    with col4:
        nr_audytu = st.text_input("🔢 Numer audytu", value="")
    
    st.text_area("📝 Dodatkowe uwagi / zakres audytu", height=100)
    st.info("ℹ️ Dane zostaną użyte w raporcie PDF.")

# ==================== TAB 1: CHECKLISTA ====================
with tab1:
    st.header("📋 Ocena zgodności wymagań BHP")
    
    # Pasek postępu
    ocenione = df_filt[df_filt["Ocena"] != ""].shape[0]
    wszystkie = df_filt.shape[0]
    if wszystkie > 0:
        progress = ocenione / wszystkie
        st.progress(progress, text=f"✅ Postęp: {int(progress*100)}% ({ocenione}/{wszystkie})")
    
    st.markdown("---")
    
    # Wyświetl każde wymaganie w osobnym wierszu z selectboxem
    for idx, row in df_filt.iterrows():
        with st.container():
            cols = st.columns([1, 2, 3, 2, 1.5, 2])
            
            # Lp
            cols[0].markdown(f"**{row['Lp']}**")
            
            # Obszar
            cols[1].write(row.get("obszar", ""))
            
            # Pytanie
            cols[2].write(row.get("pytanie", ""))
            
            # --- Podstawa prawna - selectbox z listy ---
            current_value = row.get("podstawa prawna", "")
            if pd.isna(current_value):
                current_value = ""
            
            # Selectbox do wyboru fragmentu aktu
            options = [""] + akty_lista
            current_index = 0
            if current_value in akty_lista:
                current_index = akty_lista.index(current_value) + 1
            
            selected_value = cols[3].selectbox(
                "Podstawa prawna",
                options=options,
                index=current_index,
                key=f"akt_{idx}_{row['Lp']}",
                label_visibility="collapsed"
            )
            
            # Jeśli zmieniono, zapisz
            if selected_value != current_value:
                df.at[idx, "podstawa prawna"] = selected_value
                save_checklist(df)
                st.rerun()
            
            # Jeśli wybrany akt ma link, wyświetl mały odnośnik
            if selected_value and selected_value in akty_linki:
                cols[3].markdown(f"[🔗 Zobacz na ISAP]({akty_linki[selected_value]})", unsafe_allow_html=True)
            
            # --- Ocena ---
            ocena_options = ["", "TAK", "NIE", "Częściowo", "Nie dotyczy"]
            current_ocena = row.get("Ocena", "")
            if pd.isna(current_ocena):
                current_ocena = ""
            ocena_index = ocena_options.index(current_ocena) if current_ocena in ocena_options else 0
            
            new_ocena = cols[4].selectbox(
                "Ocena",
                options=ocena_options,
                index=ocena_index,
                key=f"ocena_{idx}_{row['Lp']}",
                label_visibility="collapsed"
            )
            
            if new_ocena != current_ocena:
                df.at[idx, "Ocena"] = new_ocena
                save_checklist(df)
                st.rerun()
            
            # --- Komentarz ---
            current_komentarz = row.get("Komentarz", "")
            if pd.isna(current_komentarz):
                current_komentarz = ""
            
            new_komentarz = cols[5].text_area(
                "Uwagi",
                value=current_komentarz,
                key=f"komentarz_{idx}_{row['Lp']}",
                label_visibility="collapsed",
                height=60
            )
            
            if new_komentarz != current_komentarz:
                df.at[idx, "Komentarz"] = new_komentarz
                save_checklist(df)
                st.rerun()
        
        st.divider()
    
    # Przycisk zapisu (awaryjny)
    if st.button("💾 Zapisz wszystkie zmiany", use_container_width=True):
        save_checklist(df)
        st.success("✅ Zapisano!")
        st.rerun()

# ==================== TAB 2: BAZA AKTÓW PRAWNYCH ====================
with tab2:
    st.header("⚖️ Baza aktów prawnych")
    
    if df_akty is not None and not df_akty.empty:
        st.subheader("📚 Dostępne akty prawne (fragmenty)")
        st.dataframe(df_akty, use_container_width=True)
        
        st.info("""
        **Jak korzystać?**
        1. W zakładce **Checklista** w kolumnie "Podstawa prawna" wybierz odpowiedni fragment z listy
        2. Jeśli dodasz link w drugiej kolumnie – pojawi się odnośnik "🔗 Zobacz na ISAP"
        
        **Aby dodać nowy fragment aktu prawnego:**
        - Edytuj arkusz **`Akty prawne`** w pliku Excel
        - W pierwszej kolumnie wpisz nazwę fragmentu (np. "Rozporządzenie UDT §3 pkt 5")
        - W drugiej kolumnie opcjonalnie wklej link z ISAP
        - Zapisz plik i prześlij na GitHub
        """)
    else:
        st.warning("Nie znaleziono arkusza 'Akty prawne' w pliku Excel.")
        with st.expander("❓ Jak dodać bazę aktów prawnych?"):
            st.markdown("""
            1. W pliku Excel utwórz nowy arkusz o nazwie **`Akty prawne`**
            2. W pierwszej kolumnie wpisz **fragmenty aktów prawnych** (np. "Rozporządzenie UDT §3 pkt 5")
            3. W drugiej kolumnie opcjonalnie wklej **link z ISAP**
            4. Zapisz plik i prześlij ponownie na GitHub
            
            **Przykład:**
            
            | A | B |
            |---|---|
            | Rozporządzenie UDT §3 pkt 5 | https://isap.sejm.gov.pl/... |
            | Rozporządzenie hałasowe §2 | https://isap.sejm.gov.pl/... |
            | PN-EN 12464-1 pkt 4.2 | |
            """)

# ==================== TAB 3: RAPORT ====================
with tab3:
    st.header("📊 Raport zgodności BHP")
    
    df_oceny = df[df["Ocena"] != ""].copy()
    niezgodne = df_oceny[df_oceny["Ocena"].isin(["NIE", "Częściowo"])].copy()
    
    # Statystyki
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Wszystkie wymagania", len(df_oceny))
    with col2:
        st.metric("Zgodne (TAK)", len(df_oceny[df_oceny["Ocena"] == "TAK"]))
    with col3:
        st.metric("Niezgodności", len(niezgodne))
    with col4:
        zgodnosc_proc = (len(df_oceny[df_oceny["Ocena"] == "TAK"]) / len(df_oceny)) * 100 if len(df_oceny) > 0 else 0
        st.metric("Poziom zgodności", f"{zgodnosc_proc:.1f}%")
    
    # Wykresy
    col_a, col_b = st.columns(2)
    with col_a:
        fig1, ax1 = plt.subplots()
        oceny_counts = df_oceny["Ocena"].value_counts()
        if not oceny_counts.empty:
            ax1.pie(oceny_counts, labels=oceny_counts.index, autopct="%1.1f%%")
            ax1.set_title("Ogólna zgodność")
            st.pyplot(fig1)
    
    with col_b:
        if "obszar" in niezgodne.columns and not niezgodne.empty:
            fig2, ax2 = plt.subplots(figsize=(10, 5))
            niezgodne_obszary = niezgodne.groupby("obszar").size()
            niezgodne_obszary.sort_values(ascending=False).plot(kind="bar", ax=ax2, color="#dc3545")
            ax2.set_xlabel("Obszar BHP")
            ax2.set_ylabel("Liczba niezgodności")
            ax2.tick_params(axis='x', rotation=45)
            ax2.set_title("Niezgodności wg obszarów")
            st.pyplot(fig2)
        else:
            st.success("✅ Brak niezgodności")
    
    # Lista niezgodności
    st.subheader("📋 Lista niezgodności")
    if not niezgodne.empty:
        kolumny_raport = ["Lp", "pytanie", "podstawa prawna", "Komentarz"]
        if "obszar" in niezgodne.columns:
            kolumny_raport.insert(1, "obszar")
        st.dataframe(niezgodne[kolumny_raport], use_container_width=True)
        
        st.subheader("🧠 Wnioski")
        if "obszar" in niezgodne.columns and not niezgodne.empty:
            najgorszy_obszar = niezgodne["obszar"].value_counts().index[0]
            st.info(f"""
            **Podsumowanie audytu BHP**  
            - Liczba niezgodności: **{len(niezgodne)}**  
            - Obszar wymagający interwencji: **{najgorszy_obszar}**  
            """)
    else:
        st.success("🎉 Brak niezgodności – pełna zgodność!")
    
    # PDF
    if st.button("📄 Generuj raport PDF", use_container_width=True):
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
        pdf.cell(200, 8, txt=f"Liczba wymagań: {len(df_oceny)}", ln=1)
        pdf.cell(200, 8, txt=f"Zgodnych: {len(df_oceny[df_oceny['Ocena']=='TAK'])}", ln=1)
        pdf.cell(200, 8, txt=f"Niezgodności: {len(niezgodne)}", ln=1)
        
        if not niezgodne.empty:
            pdf.ln(5)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(200, 10, txt="Wykaz niezgodności", ln=1)
            pdf.set_font("Arial", "B", 9)
            pdf.cell(20, 8, "LP", 1)
            pdf.cell(80, 8, "Wymaganie", 1)
            pdf.cell(90, 8, "Podstawa prawna", 1)
            pdf.ln()
            pdf.set_font("Arial", size=8)
            for _, row in niezgodne.iterrows():
                pdf.cell(20, 6, str(row["Lp"]), 1)
                pytanie = row.get("pytanie", "")[:40] if pd.notna(row.get("pytanie")) else ""
                pdf.cell(80, 6, pytanie, 1)
                podstawa = row.get("podstawa prawna", "")[:50] if pd.notna(row.get("podstawa prawna")) else ""
                pdf.cell(90, 6, podstawa, 1)
                pdf.ln()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdf.output(tmp.name)
            with open(tmp.name, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            href = f'<a href="data:application/octet-stream;base64,{b64}" download="raport_bhp_{datetime.now().strftime("%Y%m%d")}.pdf">📥 Pobierz PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
            st.success("✅ Raport wygenerowany!")

st.sidebar.markdown("---")
st.sidebar.caption(f"© BHP Audyt | {len(df)} wymagań | Oceniono: {df[df['Ocena']!=''].shape[0]}")