import streamlit as st
import pandas as pd

st.set_page_config(page_title="BHP - Diagnostyka", layout="wide")

st.title("🔧 Diagnostyka pliku Excel BHP")

try:
    # Wczytaj plik
    xl = pd.ExcelFile("wymagania_bhp.xlsx")
    st.success(f"✅ Plik wczytany pomyślnie")
    st.write(f"**Znalezione arkusze:** {xl.sheet_names}")
    
    for sheet in xl.sheet_names:
        st.subheader(f"📄 Arkusz: {sheet}")
        df = pd.read_excel(xl, sheet_name=sheet)
        st.write(f"**Liczba wierszy:** {len(df)}")
        st.write(f"**Nazwy kolumn:** {list(df.columns)}")
        st.dataframe(df.head(5))
        st.divider()
        
except Exception as e:
    st.error(f"❌ Błąd: {e}")
    st.info("Upewnij się, że plik nazywa się 'wymagania_bhp.xlsx' i znajduje się w głównym folderze aplikacji")