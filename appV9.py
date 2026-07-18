import streamlit as st

# --- Importaciones locales ---
from database import load_db, save_db, DEFAULT_SETTINGS
from music_engine import generate_midi
from ui_components import inject_mobile_hack, render_midi_player

# Habilitar hack para móvil
inject_mobile_hack()

# Inicializar DB
db = load_db()

def clean_edit_cache():
    for key in ["in_ed_name", "in_ed_pat", "widget_selector"]:
        if key in st.session_state: del st.session_state[key]

# ==============================
# LÓGICA DE FILTRADO
# ==============================
user_playlists = [p for p in db["playlists"] if p != "Archivar"]
all_filters = ["Todas"] + user_playlists + ["📦 Archivados"]

default_filter = db.get("last_selected_filter", "Todas")
if default_filter not in all_filters: default_filter = "Todas"

selected_filter = st.selectbox("📂 Ver carpeta:", all_filters, index=all_filters.index(default_filter))

if selected_filter != db["last_selected_filter"]:
    db["last_selected_filter"] = selected_filter
    save_db(db)

# Filtrar ejercicios
if selected_filter == "Todas":
    available_exs = sorted([name for name, d in db["exercises"].items() if "Archivar" not in d["playlists"]])
elif selected_filter == "📦 Archivados":
    available_exs = sorted([name for name, d in db["exercises"].items() if "Archivar" in d["playlists"]])
else:
    available_exs = sorted([name for name, d in db["exercises"].items() if selected_filter in d["playlists"] and "Archivar" not in d["playlists"]])

if not available_exs:
    st.info(f"No hay ejercicios en la categoría '{selected_filter}'.")
    st.stop()

# Ejercicio seleccionado
if "selected_ex" not in st.session_state or st.session_state.selected_ex not in available_exs:
    last_ex = db.get("last_selected_exercise")
    st.session_state.selected_ex = last_ex if last_ex in available_exs else available_exs[0]
    db["last_selected_exercise"] = st.session_state.selected_ex
    save_db(db)

def sync_selection():
    st.session_state.selected_ex = st.session_state.widget_selector
    db["last_selected_exercise"] = st.session_state.selected_ex
    save_db(db)
    clean_edit_cache()

exercise = st.selectbox(
    "Selecciona el ejercicio", 
    options=available_exs,
    index=available_exs.index(st.session_state.selected_ex),
    key="widget_selector",
    on_change=sync_selection
)

# ==============================
# MENÚS ADMINISTRACIÓN
# ==============================
col_admin1, col_admin2 = st.columns(2)

with col_admin1:
    with st.popover("🛠️ Modificar BD"):
        tab_edit, tab_new, tab_del, tab_order = st.tabs(["✏️ Editar", "➕ Crear", "🗑️ Borrar", "🔄 Ordenar"])

        with tab_edit:
            edit_name = st.text_input("Nombre:", value=exercise)
            edit_pat = st.text_area("Patrón musical:", value=db["exercises"][exercise]["pattern"], height=100)
            if st.button("Guardar cambios", type="primary", use_container_width=True):
                if edit_name.strip() and edit_pat.strip():
                    db["exercises"][edit_name.strip()] = db["exercises"].pop(exercise)
                    db["exercises"][edit_name.strip()]["pattern"] = edit_pat.strip()
                    db["last_selected_exercise"] = edit_name.strip()
                    save_db(db)
                    clean_edit_cache()
                    st.rerun()

        with tab_new:
            new_name = st.text_input("Nombre:")
            new_pat = st.text_area("Patrón:", height=100)
            if st.button("Crear", type="primary", use_container_width=True):
                if new_name.strip() and new_name.strip() not in db["exercises"]:
                    db["exercises"][new_name.strip()] = {"pattern": new_pat.strip(), "settings": dict(DEFAULT_SETTINGS), "playlists": []}
                    db["last_selected_exercise"] = new_name.strip()
                    save_db(db)
                    clean_edit_cache()
                    st.rerun()

        with tab_del:
            st.warning(f"¿Borrar '{exercise}'?")
            if st.button("Sí, borrar", use_container_width=True):
                del db["exercises"][exercise]
                db["last_selected_exercise"] = list(db["exercises"].keys())[0] if db["exercises"] else ""
                save_db(db)
                clean_edit_cache()
                st.rerun()

        with tab_order:
            st.caption("Cambiar posición (aplica a 'Todas'):")
            keys = list(db["exercises"].keys())
            for i, k in enumerate(keys):
                c1, c2, c3 = st.columns([6, 1.5, 1.5])
                c1.write(k)
                if c2.button("🔼", key=f"up_{k}", disabled=(i == 0)):
                    keys[i], keys[i-1] = keys[i-1], keys[i]
                    db["exercises"] = {key: db["exercises"][key] for key in keys}
                    save_db(db)
                    st.rerun()
                if c3.button("🔽", key=f"dw_{k}", disabled=(i == len(keys)-1)):
                    keys[i], keys[i+1] = keys[i+1], keys[i]
                    db["exercises"] = {key: db["exercises"][key] for key in keys}
                    save_db(db)
                    st.rerun()

with col_admin2:
    with st.popover("📁 Playlists & Archivo"):
        is_archived = "Archivar" in db["exercises"][exercise]["playlists"]
        
        if st.button("🔄 Desarchivar" if is_archived else "📦 Archivar", use_container_width=True):
            if is_archived: db["exercises"][exercise]["playlists"].remove("Archivar")
            else: db["exercises"][exercise]["playlists"].append("Archivar")
            save_db(db)
            st.rerun()
            
        st.divider()
        current_pl = [p for p in db["exercises"][exercise]["playlists"] if p != "Archivar"]
        selected_pl = st.multiselect("Etiquetas:", user_playlists, default=current_pl)
        if set(selected_pl) != set(current_pl):
            db["exercises"][exercise]["playlists"] = selected_pl + (["Archivar"] if is_archived else [])
            save_db(db)
            
        new_pl = st.text_input("Crear nueva categoría:")
        if st.button("Crear y agregar", use_container_width=True) and new_pl:
            if new_pl not in db["playlists"]: db["playlists"].append(new_pl.strip())
            db["exercises"][exercise]["playlists"].append(new_pl.strip())
            save_db(db)
            st.rerun()

# ==============================
# CONFIGURACIONES (Auto-guardado)
# ==============================
stgs = db["exercises"][exercise]["settings"]
db_changed = False

def get_idx(options, val): return options.index(val) if val in options else 0

with st.popover("Rango, Dirección y BPM"):
    col1, col2 = st.columns(2)
    opts_low = ["A2","A#2","B2","C3","C#3","D3","D#3","E3","F3","F#3","G3","G#3","A3","A#3","B3","C4","C#4","D4","D#4","E4","F4","F#4","G4","G#4","A4"]
    opts_high = ["A4","G#4","G4","F#4","F4","E4","D#4","D4","C#4","C4","B3","A#3","A3","G#3","G3","F#3","F3","E3","D#3","D3","C#3","C3","B3","A#2","A2", "----------","D5","C#5","C5","B4","A#4"]
    opts_dir = ["ascend_descend","descend_ascend","ascend_only","descend_only"]

    with col1: range_low = st.selectbox("LOW", opts_low, index=get_idx(opts_low, stgs.get("range_low")))
    with col2: range_high = st.selectbox("HIGH", opts_high, index=get_idx(opts_high, stgs.get("range_high")))
    direction = st.selectbox("Dirección", opts_dir, index=get_idx(opts_dir, stgs.get("direction")))
    bpm = st.slider("BPM", 0, 400, stgs.get("bpm", 200), 5)

with st.popover("Otras configuraciones"):
    bridge = st.slider("Puente", 0, 32, stgs.get("bridge", 4), 1)
    metronome_vol = st.slider("Metrónomo", 0, 127, stgs.get("metronome_vol", 80), 10)
    notes_vol = st.slider("Notas Vol.", 0, 127, stgs.get("notes_vol", 127), 10)
    final_chord_vol = st.slider("Chord Vol.", 0, 127, stgs.get("final_chord_vol", 85), 10)

for key, val in [("range_low", range_low), ("range_high", range_high), ("direction", direction), ("bpm", bpm), 
                 ("bridge", bridge), ("metronome_vol", metronome_vol), ("notes_vol", notes_vol), ("final_chord_vol", final_chord_vol)]:
    if stgs.get(key) != val:
        stgs[key] = val
        db_changed = True

if db_changed: save_db(db)

# ==============================
# BOTÓN PARA GENERAR MIDI
# ==============================
if st.button("Generar MIDI"):
    try:
        # Llama a la lógica matemática pesada sólo aquí
        file_name, midi_uri = generate_midi(
            exercise, 
            db["exercises"][exercise]["pattern"], 
            stgs
        )
        st.success(f"✅ {file_name}")
        
        # Renderiza el HTML pesado sólo aquí
        render_midi_player(midi_uri)
    except Exception as e:
        st.error(f"❌ Error de sintaxis en el patrón musical: {e}")
