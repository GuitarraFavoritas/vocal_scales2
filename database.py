import os
import streamlit as st
from supabase import create_client, Client

DEFAULT_SETTINGS = {
    "range_low": "A2", "range_high": "C5", "direction": "ascend_descend",
    "bpm": 200, "bridge": 4, "metronome_vol": 80, "notes_vol": 127, "final_chord_vol": 85
}

@st.cache_resource
def init_connection() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            st.error("❌ Faltan credenciales de Supabase.")
            st.stop()
    return create_client(url, key)

supabase_client = init_connection()

if "db_version" not in st.session_state:
    st.session_state.db_version = 0

@st.cache_data(ttl=300)
def load_db_cached(version):
    try:
        response = supabase_client.table("app_state").select("data").eq("id", 1).execute()
        data = response.data[0]["data"] if response.data else {}
    except Exception as e:
        st.error(f"Error base de datos: {e}")
        data = {}

    if "exercises" not in data: data["exercises"] = {}
    if "playlists" not in data: data["playlists"] = ["Archivar"]
    if "Archivar" not in data["playlists"]: data["playlists"].insert(0, "Archivar")
    if "last_selected_filter" not in data: data["last_selected_filter"] = "Todas"

    if not data["exercises"]:
        data["exercises"]["Ejercicio de Prueba"] = {
            "pattern": "1, 2, 3, 2, 1", 
            "settings": dict(DEFAULT_SETTINGS), 
            "playlists": []
        }

    if "last_selected_exercise" not in data or data["last_selected_exercise"] not in data["exercises"]: 
        data["last_selected_exercise"] = list(data["exercises"].keys())[0]

    for k, v in data.get("exercises", {}).items():
        if "settings" not in v: v["settings"] = dict(DEFAULT_SETTINGS)
        if "playlists" not in v: v["playlists"] = []
    
    return data

def load_db():
    return load_db_cached(st.session_state.db_version)

def save_db(data):
    try:
        supabase_client.table("app_state").update({"data": data}).eq("id", 1).execute()
        st.session_state.db_version += 1 
    except Exception as e:
        st.error(f"Error al guardar en la nube: {e}")