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
    
    # Checklista
    df_checklista = pd.read_excel(xl, sheet_name="Checklista")
    df_checklista.columns = df_checklista.columns.str.strip()
    
    # Akty prawne
    df_akty = None
    if "Akty prawne" in sheet_names:
        df_akty = pd.read_excel(xl, sheet_name="Akty prawne")
        df_akty.columns = df_akty.columns.str.strip()
    
    return df_checklista, df_akty

def save_checklist(df):
    with pd.ExcelWriter("wymagania_bhp.xlsx", engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        df.to_excel(writer, sheet_name="Checklista", index=False)

df, df_akty = load_data()

# ==================== PRZYGOTOWANIE LISTY AKTÓW PRAWNYCH ====================
akty_lista = []
akty_linki = {}

if df_akty is not None and not df_akty.empty:
    # Szukamy kolumn: Lp, Akt prawny, Link
    if "Akt prawny" in df_akty.columns:
        akty_lista = df_akty["Akt prawny"].dropna().astype(str).tolist()
    elif len(df_akty.columns) >= 2:
        akty_lista = df_akty.iloc[:, 1].dropna().astype(str).tolist()
    
    if "Link" in df_akty.columns:
        for _, row in df_akty.iterrows():
            nazwa = str(row["Akt prawny"]) if pd.notna(row.get("Akt prawny")) else ""
            link = str(row["Link"]) if pd.notna(row.get("Link")) else ""
            if nazwa and link.startswith("http"):
                akty_linki[nazwa] = link
    elif len(df_akty.columns) >= 3:
        for _, row in df_akty.iterrows():
            nazwa = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
            link = str(row.iloc[2]) if pd.notna(row.iloc[2]) else ""
            if nazwa and link.startswith("http"):
                akty_linki[nazwa] = link

# ==================== FUNKCJA DO OCENY ====================
def determine_ocena(row):
    # Sprawdź kolumnę "Tak"
    if "Tak" in row and str(row["Tak"]).lower() in ["x", "tak", "1", "true", "yes"]:
        return "TAK"
    # Sprawdź kolumnę "Nie"
    elif "Nie" in row and str(row["Nie"]).lower() in ["x", "nie", "1", "false", "no"]:
        return "NIE"
    # Sprawdź kolumnę "Nie dotyczy" - akceptuje n/d, N/D, nd, ND
    elif "Nie dotyczy" in row and str(row["Nie dotyczy"]).lower() in ["x", "n/d", "nd", "1", "tak"]:
        return "Nie dotyczy"
    return ""

# Wypełnij oceny na podstawie kolumn Tak/Nie/Nie dotyczy
if "Tak" in df.columns and "Nie" in df.columns:
    df["Ocena"] = df.apply(determine_ocena, axis=1)

# Upewnij się, że kolumna Komentarz istnieje (mapowanie z "Obserwacje uwagi")
if "Obserwacje uwagi" in df.columns and "Komentarz" not in df.columns:
    df["Komentarz"] = df["Obserwacje uwagi"]
elif "Komentarz" not in df.columns:
    df["Komentarz"] = ""

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
    
    # Logo
    col_logo, col_title = st.columns([1, 3])
    with col_logo:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=120)
        else:
            st.info("📌 Miejsce na logo\n(dodaj plik logo.png)")
    
    with col_title:
        st.markdown("<h1 style='text-align: center;'>Ocena zgodności z wymaganiami prawnymi w wybranych obszarach</h1>", unsafe_allow_html=True)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        zaklad = st.text_input("🏭 **Zakład**", value="", placeholder="Wpisz nazwę zakładu pracy")
        data_audytu = st.date_input("📅 **Data**", value=datetime.now().date())
    with col2:
        imie_nazwisko = st.text_input("👤 **Oceniający (imię i nazwisko)**", value="", placeholder="Jan Kowalski")
        stanowisko = st.text_input("📌 **Stanowisko**", value="", placeholder="Specjalista BHP")
    
    if zaklad:
        st.success(f"✅ Audyt dla: **{zaklad}**")
    if imie_nazwisko and stanowisko:
        st.info(f"👤 Oceniający: **{imie_nazwisko}**, stanowisko: **{stanowisko}**")

# ==================== TAB 1: CHECKLISTA ====================
with tab1:
    st.header("📋 Ocena zgodności wymagań BHP")
    
    # Pasek postępu
    ocenione = df_filt[df_filt["Ocena"] != ""].shape[0]
    wszystkie = df_filt.shape[0]
    if wszystkie > 0:
        progress = ocenione / wszystkie
        st.progress(progress, text=f"✅ Postęp oceny: {int(progress*100)}% ({ocenione}/{wszystkie})")
    
    st.markdown("---")
    
    # Wyświetl każde wymaganie w osobnym wierszu
    for idx, row in df_filt.iterrows():
        with st.container():
            cols = st.columns([0.5, 1.5, 2.5, 2, 1, 1.5])
            
            # Lp
            cols[0].markdown(f"**{row['Lp']}**")
            
            # Obszar
            cols[1].write(row.get("Obszar", ""))
            
            # Pytanie
            cols[2].write(row.get("Pytanie", ""))
            
            # --- Podstawa prawna - selectbox ---
            current_value = row.get("Podstawa prawna", "")
            if pd.isna(current_value):
                current_value = ""
            
            if akty_lista:
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
                
                if selected_value != current_value:
                    df.at[idx, "Podstawa prawna"] = selected_value
                    save_checklist(df)
                    st.rerun()
                
                if selected_value and selected_value in akty_linki:
                    cols[3].markdown(f"[🔗 Zobacz akt prawny]({akty_linki[selected_value]})", unsafe_allow_html=True)
            else:
                cols[3].write(current_value)
            
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
                # Aktualizuj odpowiednią kolumnę w Excelu (Tak/Nie/Nie dotyczy)
                if "Tak" in df.columns:
                    df.at[idx, "Tak"] = "x" if new_ocena == "TAK" else ""
                if "Nie" in df.columns:
                    df.at[idx, "Nie"] = "x" if new_ocena == "NIE" else ""
                if "Nie dotyczy" in df.columns:
                    df.at[idx, "Nie dotyczy"] = "n/d" if new_ocena == "Nie dotyczy" else ""
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
                if "Obserwacje uwagi" in df.columns:
                    df.at[idx, "Obserwacje uwagi"] = new_komentarz
                save_checklist(df)
                st.rerun()
        
        st.divider()
    
    if st.button("💾 Zapisz wszystkie zmiany", use_container_width=True):
        save_checklist(df)
        st.success("✅ Zapisano!")
        st.rerun()

# ==================== TAB 2: AKTY PRAWNE ====================
with tab2:
    st.header("⚖️ Akty prawne")
    
    if df_akty is not None and not df_akty.empty:
        st.subheader("📚 Baza aktów prawnych")
        st.dataframe(df_akty, use_container_width=True)
        
        st.info("""
        **💡 Jak korzystać?**
        - W zakładce **Checklista** w kolumnie "Podstawa prawna" wybierz akt z listy
        - Jeśli w kolumnie "Link" podałeś adres URL – pojawi się odnośnik "🔗 Zobacz akt prawny"
        
        **✏️ Aby dodać nowy akt prawny:**
        - Edytuj arkusz **Akty prawne** w pliku Excel
        - Wypełnij kolumny: Lp, Akt prawny, Link
        - Zapisz plik i prześlij na GitHub
        """)
    else:
        st.warning("Nie znaleziono arkusza 'Akty prawne' w pliku Excel.")
        with st.expander("❓ Jak dodać bazę aktów prawnych?"):
            st.markdown("""
            1. W pliku Excel utwórz nowy arkusz o nazwie **`Akty prawne`**
            2. Dodaj trzy kolumny: **Lp**, **Akt prawny**, **Link**
            3. Wypełnij dane:
               - Lp: numer porządkowy
               - Akt prawny: np. "Rozporządzenie UDT §3 pkt 5"
               - Link: opcjonalny link z ISAP
            4. Zapisz plik i prześlij ponownie na GitHub
            """)

# ==================== TAB 3: RAPORT ====================
with tab3:
    st.header("📊 Raport zgodności BHP")
    
    df_oceny = df[df["Ocena"] != ""].copy()
    niezgodne = df_oceny[df_oceny["Ocena"] == "NIE"].copy()
    czesciowe = df_oceny[df_oceny["Ocena"] == "Częściowo"].copy()
    
    # Statystyki
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Wszystkie wymagania", len(df_oceny))
    with col2:
        st.metric("Zgodne (TAK)", len(df_oceny[df_oceny["Ocena"] == "TAK"]))
    with col3:
        st.metric("Niezgodności (NIE)", len(niezgodne))
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
        if "Obszar" in niezgodne.columns and not niezgodne.empty:
            fig2, ax2 = plt.subplots(figsize=(10, 5))
            niezgodne_obszary = niezgodne.groupby("Obszar").size()
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
        kolumny_raport = ["Lp", "Pytanie", "Podstawa prawna", "Komentarz"]
        if "Obszar" in niezgodne.columns:
            kolumny_raport.insert(1, "Obszar")
        st.dataframe(niezgodne[kolumny_raport], use_container_width=True)
        
        st.subheader("🧠 Wnioski")
        if "Obszar" in niezgodne.columns and not niezgodne.empty:
            najgorszy_obszar = niezgodne["Obszar"].value_counts().index[0]
            st.info(f"""
            **Podsumowanie audytu BHP**  
            - Łączna liczba niezgodności: **{len(niezgodne)}**  
            - Obszar wymagający interwencji: **{najgorszy_obszar}**  
            - Zalecane działania: korekta niezgodności, aktualizacja dokumentacji.
            """)
        else:
            st.info(f"Łączna liczba niezgodności: **{len(niezgodne)}**")
    else:
        st.success("🎉 Brak niezgodności – pełna zgodność!")
    
    # Generowanie PDF
    if st.button("📄 Generuj raport PDF", use_container_width=True):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(200, 10, txt="Raport oceny zgodności BHP", ln=1, align="C")
        pdf.set_font("Arial", size=10)
        pdf.cell(200, 10, txt=f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=1, align="C")
        pdf.ln(10)
        
        pdf.set_font("Arial", "B", 12)
        pdf.cell(200, 10, txt="Podsumowanie statystyczne", ln=1)
        pdf.set_font("Arial", size=10)
        pdf.cell(200, 8, txt=f"Liczba wymagań: {len(df_oceny)}", ln=1)
        pdf.cell(200, 8, txt=f"Zgodnych (TAK): {len(df_oceny[df_oceny['Ocena']=='TAK'])}", ln=1)
        pdf.cell(200, 8, txt=f"Niezgodności (NIE): {len(niezgodne)}", ln=1)
        pdf.cell(200, 8, txt=f"Poziom zgodności: {zgodnosc_proc:.1f}%", ln=1)
        
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
                pytanie = row.get("Pytanie", "")[:40] if pd.notna(row.get("Pytanie")) else ""
                pdf.cell(80, 6, pytanie, 1)
                podstawa = row.get("Podstawa prawna", "")[:50] if pd.notna(row.get("Podstawa prawna")) else ""
                pdf.cell(90, 6, podstawa, 1)
                pdf.ln()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdf.output(tmp.name)
            with open(tmp.name, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            href = f'<a href="data:application/octet-stream;base64,{b64}" download="raport_bhp_{datetime.now().strftime("%Y%m%d")}.pdf">📥 Pobierz raport PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
            st.success("✅ Raport wygenerowany!")

st.sidebar.markdown("---")
st.sidebar.caption(f"© BHP Audyt | Liczba wymagań: {len(df)} | Oceniono: {df[df['Ocena']!=''].shape[0]}")