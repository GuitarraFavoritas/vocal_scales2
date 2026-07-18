import streamlit.components.v1 as components

def inject_mobile_hack():
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

def render_midi_player(midi_uri):
    html_player = f"""
    <!DOCTYPE html><html><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://cdn.jsdelivr.net/combine/npm/tone@14.7.58,npm/@magenta/music@1.23.1/es6/core.js,npm/focus-visible@5,npm/html-midi-player@1.5.0"></script>
    <style>
        * {{ box-sizing: border-box; }} 
        body {{ margin: 0; padding: 0; width: 100vw; background-color: #121212; overflow-x: hidden; font-family: sans-serif; }} 
        midi-player {{ width: 100%; display: block; margin-top: 10px; }}
        #note-display-wrapper {{ display: flex; justify-content: center; margin: 10px 0 5px 0; }}
        #note-display {{
            font-size: 2.5rem; font-weight: 900; color: #444; 
            background: #1a1a1a; padding: 10px 50px; 
            border-radius: 12px; border: 2px solid #333;
            min-width: 160px; text-align: center;
            transition: all 0.05s ease-out;
        }}
        #note-display.active {{
            color: #FFD700; border-color: #FFD700;
            text-shadow: 0 0 15px rgba(255, 215, 0, 0.6);
            transform: scale(1.05);
        }}
    </style>
    </head><body>
    <div style="display: flex; flex-direction: column; width: 100%; gap: 5px; padding: 5px;">
        <div id="note-display-wrapper"><div id="note-display">--</div></div>
        <midi-player src="{midi_uri}" sound-font></midi-player>
    </div>
    <script>
        const notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
        function getNoteName(pitch) {{
            const octave = Math.floor(pitch / 12) - 1;
            return notes[pitch % 12] + octave;
        }}
        const noteDisplay = document.getElementById('note-display');
        const player = document.querySelector('midi-player');
        let animationId;
        let currentActiveNote = null;

        function checkPlaybackTime() {{
            if (player.playing && player.noteSequence) {{
                const time = player.currentTime;
                const activeNotes = player.noteSequence.notes.filter(n => time >= n.startTime && time < n.endTime && !n.isDrum);

                if (activeNotes.length > 0) {{
                    const note = activeNotes[0];
                    if (currentActiveNote !== note) {{
                        currentActiveNote = note;
                        noteDisplay.innerText = getNoteName(note.pitch);
                        noteDisplay.classList.remove('active');
                        void noteDisplay.offsetWidth; 
                    }}
                    if (time < note.endTime - 0.02) {{ noteDisplay.classList.add('active'); }} 
                    else {{ noteDisplay.classList.remove('active'); }}
                }} else {{
                    if (currentActiveNote !== null) {{
                        currentActiveNote = null;
                        noteDisplay.innerText = "--";
                        noteDisplay.classList.remove('active');
                    }}
                }}
            }}
            animationId = requestAnimationFrame(checkPlaybackTime);
        }}
        player.addEventListener('start', () => {{ currentActiveNote = null; animationId = requestAnimationFrame(checkPlaybackTime); }});
        player.addEventListener('stop', () => {{ cancelAnimationFrame(animationId); currentActiveNote = null; noteDisplay.innerText = "--"; noteDisplay.classList.remove('active'); }});
    </script>
    </body></html>
    """
    components.html(html_player, height=170)