import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import tempfile
import os
import base64
from datetime import datetime
import shutil
from PIL import Image
import io

st.set_page_config(page_title="BHP Professional - Ocena zgodności", layout="wide")

# ==================== KONFIGURACJA ====================
if "zdjecia" not in st.session_state:
    st.session_state.zdjecia = {}

def load_data():
    df = pd.read_excel("wymagania_bhp.xlsx", sheet_name="Checklista")
    required_cols = ["Lp", "Obszar_BHP", "Wymaganie", "Podstawa_prawna", 
                     "Sposób_weryfikacji", "Priorytet", "Ocena", "Komentarz", "Zdjęcie"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = "" if col != "Priorytet" else "Średni"
    return df

def save_data(df):
    df.to_excel("wymagania_bhp.xlsx", sheet_name="Checklista", index=False)

def color_row(ocena):
    if ocena == "TAK":
        return "background-color: #d4edda"
    elif ocena == "NIE":
        return "background-color: #f8d7da"
    elif ocena == "Częściowo":
        return "background-color: #fff3cd"
    return ""

df = load_data()

# ==================== SIDEBAR ====================
st.sidebar.header("⚙️ Panel sterowania")
obszary = ["Wszystkie"] + sorted(df["Obszar_BHP"].unique().tolist())
wybrany_obszar = st.sidebar.selectbox("Obszar BHP", obszary)

tylko_niezgodne = st.sidebar.toggle("🔴 Pokaż tylko niezgodne (NIE/Częściowo)")

if wybrany_obszar != "Wszystkie":
    df_filt = df[df["Obszar_BHP"] == wybrany_obszar]
else:
    df_filt = df.copy()

if tylko_niezgodne:
    df_filt = df_filt[df_filt["Ocena"].isin(["NIE", "Częściowo"])]

# ==================== ZAKŁADKI ====================
tab1, tab2, tab3, tab4 = st.tabs(["📋 Checklista", "⚖️ Podstawy prawne", "📸 Dokumentacja", "📊 Raport"])

# ==================== TAB 1: CHECKLISTA ====================
with tab1:
    st.header("📋 Ocena zgodności wymagań BHP")
    
    # Pasek postępu
    ocenione = df_filt[df_filt["Ocena"] != ""].shape[0]
    wszystkie = df_filt.shape[0]
    if wszystkie > 0:
        progress = ocenione / wszystkie
        st.progress(progress, text=f"✅ Postęp oceny: {int(progress*100)}% ({ocenione}/{wszystkie})")
    
    # Edytowalna tabela
    edited_df = st.data_editor(
        df_filt[["Lp", "Obszar_BHP", "Wymaganie", "Podstawa_prawna", 
                 "Sposób_weryfikacji", "Priorytet", "Ocena", "Komentarz"]],
        column_config={
            "Ocena": st.column_config.SelectboxColumn(
                "Ocena",
                options=["", "TAK", "NIE", "Częściowo", "Nie dotyczy"],
                required=False,
            ),
            "Priorytet": st.column_config.SelectboxColumn(
                "Priorytet",
                options=["Niski", "Średni", "Wysoki"],
                required=True,
            ),
            "Komentarz": st.column_config.TextColumn("Komentarz"),
            "Wymaganie": st.column_config.TextColumn("Wymaganie", width="large"),
        },
        hide_index=True,
        use_container_width=True,
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Zapisz oceny", use_container_width=True):
            for idx, row in edited_df.iterrows():
                mask = (df["Lp"] == row["Lp"]) & (df["Obszar_BHP"] == row["Obszar_BHP"])
                df.loc[mask, "Ocena"] = row["Ocena"]
                df.loc[mask, "Komentarz"] = row["Komentarz"]
                df.loc[mask, "Priorytet"] = row["Priorytet"]
            save_data(df)
            st.success("✅ Zapisano! Wykresy i raport zaktualizują się automatycznie.")
            st.rerun()
    
    with col2:
        if st.button("🔄 Resetuj filtry", use_container_width=True):
            st.session_state.clear()
            st.rerun()

# ==================== TAB 2: PODSTAWY PRAWNE ====================
with tab2:
    st.header("⚖️ Podstawy prawne z przypisanymi wymaganiami")
    
    akty = df[df["Podstawa_prawna"] != ""][["Podstawa_prawna", "Wymaganie", "Obszar_BHP", "Lp"]]
    akty_grup = akty.groupby("Podstawa_prawna").agg({
        "Wymaganie": list,
        "Lp": list,
        "Obszar_BHP": lambda x: list(set(x))
    }).reset_index()
    
    for i, row in akty_grup.iterrows():
        with st.expander(f"📜 {row['Podstawa_prawna']}"):
            st.write(f"**Obszary:** {', '.join(row['Obszar_BHP'])}")
            st.write("**Wymagania:**")
            for req, lp in zip(row["Wymaganie"], row["Lp"]):
                st.write(f"- LP {lp}: {req}")
            
            if st.button(f"🔍 Podświetl wymagania", key=f"akt_{i}"):
                st.session_state.highlight_akt = row["Podstawa_prawna"]
                st.success(f"Przejdź do zakładki 'Checklista' – podświetlono wymagania z {row['Podstawa_prawna']}")
    
    # Podświetlenie w checkliście
    if "highlight_akt" in st.session_state:
        with tab1:
            st.info(f"🔆 Podświetlone wymagania dla: {st.session_state.highlight_akt}")
            highlight_df = df_filt[df_filt["Podstawa_prawna"] == st.session_state.highlight_akt]
            if not highlight_df.empty:
                st.dataframe(highlight_df[["Lp", "Wymaganie", "Podstawa_prawna", "Ocena"]])
            else:
                st.warning("Brak wymagań dla tego aktu w obecnym filtrze")

# ==================== TAB 3: DOKUMENTACJA ZDJĘCIOWA ====================
with tab3:
    st.header("📸 Dokumentacja niezgodności")
    
    # Wybór wymagania do zdjęcia
    wymagania_list = df[df["Ocena"].isin(["NIE", "Częściowo"])][["Lp", "Wymaganie", "Obszar_BHP"]]
    if not wymagania_list.empty:
        wybor = st.selectbox(
            "Wybierz wymaganie (NIE/Częściowo) – dodaj zdjęcie",
            wymagania_list.apply(lambda x: f"{x['Lp']} - {x['Wymaganie'][:50]}", axis=1).tolist()
        )
        lp_wybrane = int(wybor.split(" - ")[0])
        
        uploaded_file = st.file_uploader("Dodaj zdjęcie (JPG/PNG)", type=["jpg", "jpeg", "png"])
        
        if uploaded_file:
            os.makedirs("zdjecia_bhp", exist_ok=True)
            filename = f"zdjecia_bhp/lp_{lp_wybrane}_{uploaded_file.name}"
            with open(filename, "wb") as f:
                f.write(uploaded_file.getbuffer())
            df.loc[df["Lp"] == lp_wybrane, "Zdjęcie"] = filename
            save_data(df)
            st.session_state.zdjecia[lp_wybrane] = filename
            st.success(f"Zdjęcie dodane dla LP {lp_wybrane}")
        
        # Podgląd zdjęć
        st.subheader("📷 Zapisane zdjęcia")
        for _, row in df[df["Zdjęcie"] != ""].iterrows():
            if os.path.exists(row["Zdjęcie"]):
                st.image(row["Zdjęcie"], caption=f"LP {row['Lp']}: {row['Wymaganie'][:50]}", width=300)
    else:
        st.info("Brak niezgodności – nie ma potrzeby dodawania zdjęć")

# ==================== TAB 4: RAPORT ====================
with tab4:
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
        st.metric("Niezgodności", len(niezgodne), delta="do poprawy")
    with col4:
        zgodnosc_proc = (len(df_oceny[df_oceny["Ocena"] == "TAK"]) / len(df_oceny)) * 100 if len(df_oceny) > 0 else 0
        st.metric("Poziom zgodności", f"{zgodnosc_proc:.1f}%")
    
    # Wykresy
    col_a, col_b = st.columns(2)
    with col_a:
        fig1, ax1 = plt.subplots()
        oceny_counts = df_oceny["Ocena"].value_counts()
        ax1.pie(oceny_counts, labels=oceny_counts.index, autopct="%1.1f%%", colors=["#28a745", "#dc3545", "#ffc107", "#6c757d"])
        ax1.set_title("Ogólna zgodność")
        st.pyplot(fig1)
    
    with col_b:
        fig2, ax2 = plt.subplots(figsize=(10, 5))
        niezgodne_obszary = niezgodne.groupby("Obszar_BHP").size()
        if not niezgodne_obszary.empty:
            niezgodne_obszary.sort_values(ascending=False).plot(kind="bar", ax=ax2, color="#dc3545")
            ax2.set_xlabel("Obszar BHP")
            ax2.set_ylabel("Liczba niezgodności")
            ax2.tick_params(axis='x', rotation=45)
            ax2.set_title("Niezgodności wg obszarów")
            st.pyplot(fig2)
        else:
            st.success("✅ Brak niezgodności – wszystko zgodne!")
    
    # Priorytety niezgodności
    st.subheader("⚠️ Niezgodności według priorytetu")
    if not niezgodne.empty:
        prio_counts = niezgodne["Priorytet"].value_counts()
        st.bar_chart(prio_counts)
        
        st.subheader("📋 Lista niezgodności (z priorytetami)")
        st.dataframe(
            niezgodne[["Lp", "Obszar_BHP", "Wymaganie", "Podstawa_prawna", "Priorytet", "Komentarz"]],
            use_container_width=True
        )
        
        # Automatyczne wnioski
        st.subheader("🧠 Automatyczne wnioski")
        najgorszy_obszar = niezgodne["Obszar_BHP"].value_counts().index[0] if not niezgodne.empty else "brak"
        wysokie_prio = niezgodne[niezgodne["Priorytet"] == "Wysoki"].shape[0]
        
        st.info(f"""
        **Podsumowanie audytu BHP**  
        - Łączna liczba niezgodności: **{len(niezgodne)}**  
        - Obszar wymagający pilnej interwencji: **{najgorszy_obszar}**  
        - Liczba niezgodności o wysokim priorytecie: **{wysokie_prio}**  
        - Zalecane działania: natychmiastowa korekta w obszarach wysokiego priorytetu, aktualizacja dokumentacji, szkolenia BHP.
        """)
    else:
        st.success("🎉 Brak niezgodności – pełna zgodność z wymaganiami BHP!")
    
    # Generowanie PDF
    if st.button("📄 Generuj profesjonalny raport PDF", use_container_width=True):
        pdf = FPDF()
        pdf.add_page()
        
        # Logo (opcjonalnie – wstaw plik logo.png w folderze)
        if os.path.exists("logo.png"):
            pdf.image("logo.png", x=10, y=8, w=30)
        
        pdf.set_font("Arial", "B", 16)
        pdf.cell(200, 10, txt="Raport oceny zgodności BHP", ln=1, align="C")
        pdf.set_font("Arial", size=10)
        pdf.cell(200, 10, txt=f"Data generowania: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=1, align="C")
        pdf.ln(10)
        
        # Statystyki
        pdf.set_font("Arial", "B", 12)
        pdf.cell(200, 10, txt="Podsumowanie statystyczne", ln=1)
        pdf.set_font("Arial", size=10)
        pdf.cell(200, 8, txt=f"Liczba wymagań: {len(df_oceny)}", ln=1)
        pdf.cell(200, 8, txt=f"Zgodnych (TAK): {len(df_oceny[df_oceny['Ocena']=='TAK'])}", ln=1)
        pdf.cell(200, 8, txt=f"Niezgodności (NIE/Częściowo): {len(niezgodne)}", ln=1)
        pdf.cell(200, 8, txt=f"Poziom zgodności: {zgodnosc_proc:.1f}%", ln=1)
        pdf.ln(5)
        
        # Tabela niezgodności z priorytetami
        if not niezgodne.empty:
            pdf.set_font("Arial", "B", 12)
            pdf.cell(200, 10, txt="Wykaz niezgodności", ln=1)
            pdf.set_font("Arial", "B", 9)
            pdf.cell(20, 8, "LP", 1)
            pdf.cell(40, 8, "Obszar", 1)
            pdf.cell(60, 8, "Wymaganie", 1)
            pdf.cell(40, 8, "Podstawa prawna", 1)
            pdf.cell(30, 8, "Priorytet", 1)
            pdf.ln()
            pdf.set_font("Arial", size=8)
            for _, row in niezgodne.iterrows():
                pdf.cell(20, 6, str(row["Lp"]), 1)
                pdf.cell(40, 6, row["Obszar_BHP"][:20], 1)
                pdf.cell(60, 6, row["Wymaganie"][:35], 1)
                pdf.cell(40, 6, row["Podstawa_prawna"][:25], 1)
                pdf.cell(30, 6, row["Priorytet"], 1)
                pdf.ln()
        
        # Zapis PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdf.output(tmp.name)
            with open(tmp.name, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            href = f'<a href="data:application/octet-stream;base64,{b64}" download="raport_bhp_{datetime.now().strftime("%Y%m%d")}.pdf">📥 Kliknij, aby pobrać raport PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
            st.success("✅ Raport wygenerowany!")

# ==================== STOPKA ====================
st.sidebar.markdown("---")
st.sidebar.caption(f"© BHP Audyt Pro | Liczba wymagań: {len(df)} | Oceniono: {df[df['Ocena']!=''].shape[0]}")