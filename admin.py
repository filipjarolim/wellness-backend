import streamlit as st
import pandas as pd
import sqlite3
import os

# Page Config
st.set_page_config(
    page_title="Wellness Admin",
    page_icon="📅",
    layout="centered"
)

# Header
st.title("Wellness Pohoda - Admin Panel")

# Database Connection
DB_FILE = "wellness.db"

def load_data():
    if not os.path.exists(DB_FILE):
        return None
    
    try:
        conn = sqlite3.connect(DB_FILE)
        # Load data sorting by ID descending (newest first)
        df = pd.read_sql_query("SELECT * FROM booking ORDER BY id DESC", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Chyba při čtení databáze: {e}")
        return None

# Load Data
if st.button("Obnovit data"):
    st.rerun()

df = load_data()

if df is not None and not df.empty:
    # Metrics
    total_bookings = len(df)
    
    # Try to verify if 'service' column exists for grouping, otherwise simple count
    unique_services = df['service'].nunique() if 'service' in df.columns else 0
    
    col1, col2 = st.columns(2)
    col1.metric("Celkový počet rezervací", total_bookings)
    col2.metric("Typy služeb", unique_services)
    
    # Data Table
    st.subheader("Seznam rezervací")
    st.dataframe(
        df, 
        use_container_width=True,
        column_config={
            "created_at": st.column_config.DatetimeColumn("Vytvořeno", format="D.M.YYYY HH:mm"),
            "day": "Den",
            "time": "Čas",
            "name": "Jméno",
            "service": "Služba",
            "id": "ID"
        }
    )
else:
    st.info("Zatím žádné rezervace nebo databáze neexistuje.")

# Footer
st.markdown("---")
st.caption("AI Voice Receptionist System • Wellness Pohoda")
