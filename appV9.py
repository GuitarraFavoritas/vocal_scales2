import base64
import json
import os
import streamlit.components.v1 as components
import streamlit as st
from midiutil import MIDIFile

# --- HACK PARA EVITAR EL TECLADO EN MÓVILES ---
components.html(
    """
    <script>
    const doc = window.parent.document;
    function disableMobileKeyboard() {
        const inputs = doc.querySelectorAll('div[data-baseweb="select"] input');
        inputs.forEach(input => {
            input.setAttribute('inputmode', 'none');
            input.setAttribute('readonly', 'readonly');
        });
    }
    disableMobileKeyboard();
    const observer = new MutationObserver(disableMobileKeyboard);
    observer.observe(doc.body, { childList: true, subtree: true });
    </script>
    """,
    height=0, width=0
)

# ==========================================
# GESTOR DE BASE DE DATOS SUPABASE (Nube)
# ==========================================
from supabase import create_client, Client
import streamlit as st

# Inicializar conexión a Supabase usando st.secrets (lo configuraremos en Streamlit Cloud)
@st.cache_resource
def init_connection():
    url = st.secrets["https://efzwcvhpooiqzjsbxvht.supabase.co/rest/v1/"]
    key = st.secrets["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVmendjdmhwb29pcXpqc2J4dmh0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI1ODM2MjEsImV4cCI6MjA5ODE1OTYyMX0.VXY5OdAtB7_Qglvxyzs_fd_Ij7AMg566sc7hg_oBTtg"]
    return create_client(url, key)

supabase_client: Client = init_connection()

DEFAULT_SETTINGS = {
    "range_low": "A2", "range_high": "C5", "direction": "ascend_descend",
    "bpm": 200, "bridge": 4, "metronome_vol": 80, "notes_vol": 127, "final_chord_vol": 85
}

def save_db(data):
    # Actualiza la fila con id=1 en la tabla 'app_state'
    try:
        supabase_client.table("app_state").update({"data": data}).eq("id", 1).execute()
    except Exception as e:
        st.error(f"Error al guardar en la nube: {e}")

def load_db():
    # Descarga la información de la base de datos
    try:
        response = supabase_client.table("app_state").select("data").eq("id", 1).execute()
        if response.data:
            data = response.data[0]["data"]
        else:
            data = {}
    except Exception as e:
        st.error(f"Error al cargar la base de datos: {e}")
        data = {}

    # Lógica de seguridad por si le faltan llaves
    if "playlists" not in data: data["playlists"] = ["Archivar"]
    if "Archivar" not in data["playlists"]: data["playlists"].insert(0, "Archivar")
    if "last_selected_filter" not in data: data["last_selected_filter"] = "Todas"
    if "last_selected_exercise" not in data: 
        data["last_selected_exercise"] = list(data.get("exercises", {}).keys())[0] if data.get("exercises") else ""

    for k, v in data.get("exercises", {}).items():
        if "settings" not in v: v["settings"] = dict(DEFAULT_SETTINGS)
        if "playlists" not in v: v["playlists"] = []
    
    return data

# Cargar la base de datos al inicio
db = load_db()

# ==============================
# NOTE HELPERS
# ==============================
note_names = {"C":0,"C#":1,"D":2,"D#":3,"E":4,"F":5,"F#":6,"G":7,"G#":8,"A":9,"A#":10,"B":11}

def note_to_midi(note):
    return 12 * (int(note[-1]) + 1) + note_names[note[:-1]]

def parse_pattern(pat):
    result = []
    for token in pat.replace(" ", "").split(","):
        if "[x" in token:
            degree, length = token.split("[x")
            length = float(length[:-1])
        else:
            degree, length = token, 1.0
        if degree.endswith("b"): result.append((int(degree[:-1]), length, -1))
        elif degree.endswith("#"): result.append((int(degree[:-1]), length, +1))
        else: result.append((int(degree), length, 0))
    return result

def build_major_scale(root_midi):
    return [root_midi + i for i in [0,2,4,5,7,9,11,12,14,16,17,19,21,23,24]]

def pattern_fits_in_range(pattern_degrees, root, high_midi):
    scale = build_major_scale(root)
    max_degree = max(deg for deg,_,_ in pattern_degrees)
    return scale[max_degree-1] <= high_midi

def clean_edit_cache():
    for key in ["in_ed_name", "in_ed_pat"]:
        if key in st.session_state: del st.session_state[key]

# ==============================
# LÓGICA DE FILTRADO Y ÚLTIMA SESIÓN
# ==============================
user_playlists = [p for p in db["playlists"] if p != "Archivar"]
all_filters = ["Todas"] + user_playlists + ["📦 Archivados"]

# Recuperar última carpeta vista
default_filter = db.get("last_selected_filter", "Todas")
if default_filter not in all_filters: default_filter = "Todas"

selected_filter = st.selectbox("📂 Ver carpeta:", all_filters, index=all_filters.index(default_filter))

# Guardar si se cambia la carpeta
if selected_filter != db["last_selected_filter"]:
    db["last_selected_filter"] = selected_filter
    save_db(db)

# Lógica de "Archivado" estilo WhatsApp
if selected_filter == "Todas":
    available_exs = [name for name, d in db["exercises"].items() if "Archivar" not in d["playlists"]]
elif selected_filter == "📦 Archivados":
    available_exs = [name for name, d in db["exercises"].items() if "Archivar" in d["playlists"]]
else:
    available_exs = [name for name, d in db["exercises"].items() if selected_filter in d["playlists"] and "Archivar" not in d["playlists"]]

if not available_exs:
    st.info(f"No hay ejercicios en la categoría '{selected_filter}'.")
    st.stop()

# Recuperar último ejercicio visto
if "selected_ex" not in st.session_state or st.session_state.selected_ex not in available_exs:
    last_ex = db.get("last_selected_exercise")
    if last_ex in available_exs:
        st.session_state.selected_ex = last_ex
    else:
        st.session_state.selected_ex = available_exs[0]
        db["last_selected_exercise"] = available_exs[0]
        save_db(db)

def sync_selection():
    st.session_state.selected_ex = st.session_state.widget_selector
    db["last_selected_exercise"] = st.session_state.selected_ex # Guardar estado al tocar selectbox
    save_db(db)
    clean_edit_cache()

current_idx = available_exs.index(st.session_state.selected_ex)

exercise = st.selectbox(
    "Selecciona el ejercicio", 
    options=available_exs,
    index=current_idx,
    key="widget_selector",
    on_change=sync_selection
)

# ==============================
# MENÚS DE ADMINISTRACIÓN (CRUD, Playlists y Orden)
# ==============================
col_admin1, col_admin2 = st.columns(2)

with col_admin1:
    with st.popover("🛠️ Modificar BD"):
        tab_edit, tab_new, tab_del, tab_order = st.tabs(["✏️ Editar", "➕ Crear", "🗑️ Borrar", "🔄 Ordenar"])

        with tab_edit:
            edit_name = st.text_input("Nombre:", value=exercise, key=f"ed_nm_{exercise}")
            edit_pat = st.text_area("Patrón musical:", value=db["exercises"][exercise]["pattern"], height=100, key=f"ed_pt_{exercise}")
            if st.button("Guardar cambios", key="btn_save_ed", type="primary", use_container_width=True):
                if not edit_name.strip() or not edit_pat.strip():
                    st.error("Campos vacíos.")
                elif edit_name != exercise and edit_name in db["exercises"]:
                    st.error("El nombre ya existe.")
                else:
                    new_dict = {}
                    for k, v in db["exercises"].items():
                        if k == exercise:
                            new_dict[edit_name.strip()] = v 
                            new_dict[edit_name.strip()]["pattern"] = edit_pat.strip()
                        else:
                            new_dict[k] = v
                    db["exercises"] = new_dict
                    db["last_selected_exercise"] = edit_name.strip()
                    save_db(db)
                    st.session_state.selected_ex = edit_name.strip()
                    if "widget_selector" in st.session_state: del st.session_state["widget_selector"]
                    st.rerun()

        with tab_new:
            new_name = st.text_input("Nombre:", key="in_nw_name")
            new_pat = st.text_area("Patrón:", height=100, key="in_nw_pat")
            if st.button("Crear ejercicio", key="btn_save_nw", type="primary", use_container_width=True):
                if new_name.strip() and new_pat.strip() and new_name.strip() not in db["exercises"]:
                    db["exercises"][new_name.strip()] = {"pattern": new_pat.strip(), "settings": dict(DEFAULT_SETTINGS), "playlists": []}
                    db["last_selected_exercise"] = new_name.strip()
                    save_db(db)
                    st.session_state.selected_ex = new_name.strip()
                    if "widget_selector" in st.session_state: del st.session_state["widget_selector"]
                    st.rerun()

        with tab_del:
            st.warning(f"¿Borrar '{exercise}'?")
            if st.button("Sí, borrar", use_container_width=True):
                del db["exercises"][exercise]
                db["last_selected_exercise"] = list(db["exercises"].keys())[0] if db["exercises"] else ""
                save_db(db)
                if "widget_selector" in st.session_state: del st.session_state["widget_selector"]
                st.rerun()

        with tab_order:
            st.caption("Cambiar posición global (aplica a 'Todas'):")
            keys = list(db["exercises"].keys())
            with st.container(height=300):
                for i, k in enumerate(keys):
                    c1, c2, c3 = st.columns([6, 1.5, 1.5])
                    c1.markdown(f"<div style='padding-top:7px; font-size:14px;'>{k}</div>", unsafe_allow_html=True)
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
        
        if is_archived:
            if st.button("🔄 Desarchivar Ejercicio", use_container_width=True):
                db["exercises"][exercise]["playlists"].remove("Archivar")
                save_db(db)
                st.rerun()
        else:
            if st.button("📦 Archivar Ejercicio", use_container_width=True):
                db["exercises"][exercise]["playlists"].append("Archivar")
                save_db(db)
                st.rerun()
            
        st.divider()
        st.caption("Agregar a otras listas:")
        current_pl = [p for p in db["exercises"][exercise]["playlists"] if p != "Archivar"]
        selected_pl = st.multiselect("Etiquetas:", user_playlists, default=current_pl, key=f"ms_{exercise}")
        
        if set(selected_pl) != set(current_pl):
            db["exercises"][exercise]["playlists"] = selected_pl + (["Archivar"] if is_archived else [])
            save_db(db)
            
        st.divider()
        new_pl = st.text_input("Crear nueva categoría:", key=f"n_pl_{exercise}")
        if st.button("Crear y agregar", use_container_width=True):
            if new_pl and new_pl not in db["playlists"]:
                db["playlists"].append(new_pl.strip())
                db["exercises"][exercise]["playlists"].append(new_pl.strip())
                save_db(db)
                st.rerun()

# ==============================
# CONFIGURACIONES (Auto-guardado ligado al ejercicio)
# ==============================
stgs = db["exercises"][exercise]["settings"]
db_changed = False

def get_idx(options, val, default=0):
    return options.index(val) if val in options else default

with st.popover("Rango, Dirección y BPM"):
    col1, col2 = st.columns(2)
    opts_low = ["A2","A#2","B2","C3","C#3","D3","D#3","E3","F3","F#3","G3","G#3","A3","A#3","B3","C4","C#4","D4","D#4","E4","F4","F#4","G4","G#4","A4"]
    opts_high = ["A4","G#4","G4","F#4","F4","E4","D#4","D4","C#4","C4","B3","A#3","A3","G#3","G3","----------","D5","C5","B4"]
    opts_dir = ["ascend_descend","descend_ascend","ascend_only","descend_only"]

    with col1:
        range_low = st.selectbox("LOW", opts_low, index=get_idx(opts_low, stgs.get("range_low")), key=f"l_{exercise}")
    with col2:
        range_high = st.selectbox("HIGH", opts_high, index=get_idx(opts_high, stgs.get("range_high")), key=f"h_{exercise}")
    
    direction = st.selectbox("Dirección", opts_dir, index=get_idx(opts_dir, stgs.get("direction")), key=f"d_{exercise}")
    bpm = st.slider("BPM", min_value=0, max_value=400, value=stgs.get("bpm", 200), step=5, key=f"b_{exercise}")

with st.popover("Otras configuraciones"):
    bridge = st.slider("Duración del puente..", min_value=0, max_value=32, value=stgs.get("bridge", 4), step=1, key=f"br_{exercise}")
    metronome_vol = st.slider("Metrónomo Vol.", min_value=0, max_value=127, value=stgs.get("metronome_vol", 80), step=10, key=f"mv_{exercise}")
    notes_vol = st.slider("Notas Vol..", min_value=0, max_value=127, value=stgs.get("notes_vol", 127), step=10, key=f"nv_{exercise}")
    final_chord_vol = st.slider("Chord Vol..", min_value=0, max_value=127, value=stgs.get("final_chord_vol", 85), step=10, key=f"fv_{exercise}")

for key, val in [("range_low", range_low), ("range_high", range_high), ("direction", direction), ("bpm", bpm), 
                 ("bridge", bridge), ("metronome_vol", metronome_vol), ("notes_vol", notes_vol), ("final_chord_vol", final_chord_vol)]:
    if stgs.get(key) != val:
        stgs[key] = val
        db_changed = True

if db_changed:
    save_db(db)

file_name = f"{exercise}_{bpm}bpm_{range_low}-{range_high}_{direction}.mid"

# ==============================
# BOTÓN PARA GENERAR MIDI
# ==============================
if st.button("Generar MIDI"):
    try:
        pattern_notes = parse_pattern(db["exercises"][exercise]["pattern"])
    except Exception:
        st.error("❌ Error de sintaxis en el patrón musical. Corrígelo en el menú Editar.")
        st.stop()

    mf = MIDIFile(2) 
    mf.addTempo(0, 0, bpm)
    mf.addTempo(1, 0, bpm)
    channel_drums, woodblock = 9, 76

    low_midi, high_midi = note_to_midi(range_low), note_to_midi(range_high)
    roots_up, root = [], low_midi
    while root <= high_midi:
        if not pattern_fits_in_range(pattern_notes, root, high_midi): break
        roots_up.append(root); root += 1

    dir_lower = direction.lower().replace(" ", "_")
    if dir_lower in ("ascend_only","low_to_high"): roots = roots_up
    elif dir_lower in ("descend_only","high_to_low"):
        start_root = high_midi
        while start_root >= low_midi and not pattern_fits_in_range(pattern_notes, start_root, high_midi): start_root -= 1
        roots = list(range(start_root, low_midi-1, -1))
    elif dir_lower in ("ascend_descend","up_down"): roots = roots_up + roots_up[-2::-1]
    elif dir_lower in ("descend_ascend","down_up"):
        roots_down = [r for r in range(high_midi, low_midi-1, -1) if pattern_fits_in_range(pattern_notes, r, high_midi)]
        roots = roots_down + roots_down[-2::-1]
    else: roots = roots_up

    time = 0
    for beat in range(4):
        mf.addNote(1, channel_drums, woodblock, time+beat, 0.5, metronome_vol)
    time += 4

    for i, root in enumerate(roots):
        scale = build_major_scale(root)
        for idx, (degree, length, accidental) in enumerate(pattern_notes, start=1):
            note_num = scale[degree-1] + accidental
            mf.addNote(0, 0, note_num, time, length, notes_vol)
            for b in range(int(length)):
                mf.addNote(1, channel_drums, woodblock, time+b, 0.5, metronome_vol)
            time += length

        if i < len(roots)-1:
            next_root = roots[i+1]
            mf.addNote(0, 0, next_root, time, bridge, notes_vol)
            for b in range(bridge): mf.addNote(1, channel_drums, woodblock, time+b, 0.5, metronome_vol)
            time += bridge

    final_scale = build_major_scale(low_midi)
    for degree,_,_ in pattern_notes:
        mf.addNote(0, 0, final_scale[degree-1], time, 4, final_chord_vol)
    for b in range(4): mf.addNote(1, channel_drums, woodblock, time+b, 0.5, metronome_vol)

    with open(file_name, "wb") as f: mf.writeFile(f)
    st.success(f"✅ {file_name}")
    
    with open(file_name, "rb") as f: midi_data = f.read()
    b64_midi = base64.b64encode(midi_data).decode("utf-8")
    midi_uri = f"data:audio/midi;base64,{b64_midi}"

    html_player = f"""
    <!DOCTYPE html><html><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://cdn.jsdelivr.net/combine/npm/tone@14.7.58,npm/@magenta/music@1.23.1/es6/core.js,npm/focus-visible@5,npm/html-midi-player@1.5.0"></script>
    <style>* {{ box-sizing: border-box; }} body {{ margin: 0; padding: 0; width: 100vw; background-color: #121212; overflow-x: hidden; }} midi-player, midi-visualizer {{ width: 100%; display: block; }}</style>
    </head><body><div style="display: flex; flex-direction: column; width: 100%; gap: 10px; padding: 2px;">
    <midi-player src="{midi_uri}" sound-font visualizer="#mobileWaterfall"></midi-player>
    <midi-visualizer type="piano roll" id="mobileWaterfall" src="{midi_uri}" config='{{"noteRGB": "0, 190, 255", "activeNoteRGB": "255, 215, 0", "pixelsPerTimeStep": 45}}' style="height: 320px; background: #121212; border-radius: 12px; border: 1px solid #333; box-shadow: inset 0 0 10px rgba(0,0,0,0.8);"></midi-visualizer>
    </div></body></html>
    """
    components.html(html_player, height=395)
    st.download_button("Descargar Archivo MIDI", data=midi_data, file_name=file_name, mime="audio/midi")