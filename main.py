import os
import datetime
from flask import Flask, redirect, request, session, jsonify, send_from_directory, Response
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
import os
import json
from uuid import uuid4

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get("FLASK_SECRET", "super_secret")


sp_oauth = SpotifyOAuth(
    client_id=os.environ["SPOTIPY_CLIENT_ID"],
    client_secret=os.environ["SPOTIPY_CLIENT_SECRET"],
    redirect_uri=os.environ["SPOTIPY_REDIRECT_URI"],
    scope="user-read-recently-played playlist-modify-private playlist-modify-public"
)

SESSIONS_FILE = 'sessions.json'

def load_sessions():
    if not os.path.exists(SESSIONS_FILE):
        return {}
    with open(SESSIONS_FILE, 'r') as f:
        return json.load(f)

def save_sessions(sessions):
    with open(SESSIONS_FILE, 'w') as f:
        json.dump(sessions, f)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/login')
def login():
    return redirect(sp_oauth.get_authorize_url())

@app.route('/callback')
def callback():
    code = request.args.get("code")
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect('/session')

@app.route('/session')
def get_session():
    token_info = session.get('token_info')
    if not token_info:
        return redirect('/login')

    sp = Spotify(auth=token_info['access_token'])
    results = sp.current_user_recently_played(limit=50)

    items = results.get('items', [])
    if not items:
        return Response("<h2>No recent tracks found</h2>", mimetype='text/html')

    tracks = []
    track_ids = []
    for item in items:
        played_at = datetime.datetime.strptime(item['played_at'], "%Y-%m-%dT%H:%M:%S.%fZ")
        played_at = played_at.replace(tzinfo=datetime.timezone.utc)
        artist = ', '.join([a['name'] for a in item['track']['artists']])
        track_id = item['track']['id']
        tracks.append((played_at, item['track']['name'], artist, track_id))
        track_ids.append(track_id)

    tracks.sort()
    session_tracks = [tracks[-1]]
    for i in range(len(tracks)-2, -1, -1):
        gap = (session_tracks[0][0] - tracks[i][0]).total_seconds()
        if gap <= 600:
            session_tracks.insert(0, tracks[i])
        else:
            break

    start = session_tracks[0][0].strftime("%H:%M")
    end = session_tracks[-1][0].strftime("%H:%M")
    duration_seconds = int((session_tracks[-1][0] - session_tracks[0][0]).total_seconds())
    duration_minutes = duration_seconds // 60
    duration_secs = duration_seconds % 60
    duration = f"{duration_minutes}:{duration_secs:02d}"
    songs = [(t[1], t[2]) for t in session_tracks]
    song_ids = [t[3] for t in session_tracks if t[3]]

    html = f"""
    <!DOCTYPE html>
    <html lang=\"en\">
    <head>
        <meta charset=\"UTF-8\" />
        <title>Spotify Session</title>
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
        <link rel=\"apple-touch-icon\" href=\"/static/icon.png\">
        <meta name=\"apple-mobile-web-app-capable\" content=\"yes\">
        <meta name=\"apple-mobile-web-app-title\" content=\"Spotify Session\">
        <meta name=\"theme-color\" content=\"#1DB954\">
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 40px auto;
                max-width: 700px;
                background: #181818;
                color: #fff;
                line-height: 1.6;
            }}
            h1 {{
                text-align: center;
                color: #1DB954;
            }}
            .logo {{
                display: block;
                margin: 0 auto 2em auto;
                width: 80px;
            }}
            .summary {{
                background: #232323;
                border: 1px solid #1DB954;
                padding: 20px;
                margin-bottom: 30px;
                border-radius: 8px;
                text-align: center;
            }}
            .summary p {{
                margin: 8px 0;
                font-size: 1.1em;
            }}
            ul.songs {{
                list-style: none;
                padding: 0;
            }}
            ul.songs li {{
                background: #282828;
                margin-bottom: 8px;
                padding: 12px 16px;
                border-radius: 6px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.15);
                transition: background 0.3s ease, color 0.3s ease;
                color: #fff;
            }}
            ul.songs li span {{
                color: #1DB954;
                transition: color 0.3s ease;
            }}
            ul.songs li:hover {{
                background: #1DB954;
                color: #181818;
            }}
            ul.songs li:hover span {{
                color: #181818;
            }}
            .playlist-link {{
                display: block;
                margin: 1em auto;
                text-align: center;
                color: #1DB954;
                font-weight: bold;
                font-size: 1.1em;
                text-decoration: underline;
            }}
            .btn {{
                background: #1DB954;
                color: #181818;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
                cursor: pointer;
                margin-top: 1em;
            }}
            .btn:hover {{ background: #181818; color: #1DB954; border: 1px solid #1DB954; }}
        </style>
        <script>
        function createPlaylist(event) {{
            event.preventDefault();
            var btn = document.getElementById('create-playlist-btn');
            btn.disabled = true;
            btn.innerText = 'Creating...';
            var form = btn.closest('form');
            var formData = new FormData(form);
            fetch('/create_playlist_from_session', {{
                method: 'POST',
                body: formData
            }})
            .then(resp => resp.text())
            .then(html => {{
                btn.parentNode.innerHTML = html;
            }});
        }}
        </script>
    </head>
    <body>
        <h1>Spotify Listening Session</h1>
        <div class="summary">
            <p><strong>Session Start Time:</strong> {start}</p>
            <p><strong>Session End Time:</strong> {end}</p>
            <p><strong>Total Duration:</strong> {duration} minutes</p>
            <p><strong>Number of Songs Played:</strong> {len(songs)}</p>
            <form action="/create_playlist_from_session" method="post" onsubmit="createPlaylist(event)">
                <input type="hidden" name="song_ids" value="{','.join(song_ids)}">
                <button class="btn" id="create-playlist-btn" type="submit">Create Playlist</button>
            </form>
        </div>
        <h2>Tracks Played</h2>
        <ul class="songs">
            {''.join(f'<li>{i+1}. {song} <span>by {artist}</span></li>' for i, (song, artist) in enumerate(songs))}
        </ul>
    </body>
    </html>
    """

    return Response(html, mimetype='text/html')

@app.route('/create_playlist_from_session', methods=['POST'])
def create_playlist_from_session():
    token_info = session.get('token_info')
    if not token_info:
        return redirect('/login')
    sp = Spotify(auth=token_info['access_token'])
    song_ids = request.form.get('song_ids', '').split(',')
    user_id = sp.current_user()['id']
    playlist = sp.user_playlist_create(user=user_id, name=f"Spotify Session {datetime.datetime.now().strftime('%Y%m%d%H%M%S')}", public=False)
    if song_ids and song_ids[0]:
        sp.playlist_add_items(playlist_id=playlist['id'], items=song_ids)
    # Devolver solo el botón para abrir la playlist
    return f"<a href='{playlist['external_urls']['spotify']}' class='btn' style='display:block;margin:1em auto 0 auto;text-align:center;' target='_blank'>Open Playlist on Spotify</a>"

@app.route('/saved_sessions')
def saved_sessions():
    token_info = session.get('token_info')
    if not token_info:
        return redirect('/login')
    sp = Spotify(auth=token_info['access_token'])
    playlists = []
    results = sp.current_user_playlists(limit=50)
    print('DEBUG: Fetched playlists:', results)  # DEBUG
    while results:
        for playlist in results['items']:
            print('DEBUG: Playlist name:', playlist['name'])  # DEBUG
            if playlist['name'].startswith('Spotify Session'):
                print('DEBUG: Matched session playlist:', playlist['name'])  # DEBUG
                playlists.append(playlist)
        if results['next']:
            results = sp.next(results)
        else:
            results = None
    print('DEBUG: Session playlists found:', len(playlists))  # DEBUG
    html = """
    <html><head><title>Saved Sessions</title>
    <meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>
    body { background: #181818; color: #fff; font-family: Arial, sans-serif; display: flex; flex-direction: column; align-items: center; min-height: 100vh; margin: 0; }
    h1 { color: #1DB954; text-align: center; margin-top: 2em; }
    .session { background: #232323; border: 1px solid #1DB954; margin: 1em 0; padding: 1em; border-radius: 8px; width: 100%; max-width: 500px; box-sizing: border-box; }
    .btn { background: #1DB954; color: #181818; border: none; border-radius: 6px; padding: 8px 18px; font-weight: bold; cursor: pointer; margin-top: 1em; }
    .btn:hover { background: #181818; color: #1DB954; border: 1px solid #1DB954; }
    a { color: #1DB954; }
    .tracks { display: none; margin-top: 1em; }
    .show { display: block; }
    .toggle-btn { background: #232323; color: #1DB954; border: 1px solid #1DB954; border-radius: 6px; padding: 4px 12px; cursor: pointer; margin-bottom: 0.5em; }
    .no-sessions { color: #888; text-align: center; margin-top: 2em; }
    </style>
    <script>
    function toggleTracks(id) {
        var el = document.getElementById('tracks-' + id);
        if (el.classList.contains('show')) {
            el.classList.remove('show');
        } else {
            el.classList.add('show');
        }
    }
    </script>
    </head><body>
    <h1>Saved Sessions</h1>
    <div style='width:100%;display:flex;flex-direction:column;align-items:center;'>
    """
    if not playlists:
        html += "<div class='no-sessions'>No saved sessions found.</div>"
    for idx, playlist in enumerate(playlists):
        html += f"""
        <div class='session'>
            <p><strong>Name:</strong> {playlist['name']}</p>
            <p><strong>Tracks:</strong> {playlist['tracks']['total']}</p>
            <a href='{playlist['external_urls']['spotify']}' target='_blank'>Open Playlist on Spotify</a><br>
            <button class='toggle-btn' onclick=\"toggleTracks('{idx}')\">Show/Hide Songs</button>
            <div class='tracks' id='tracks-{idx}'>Loading...</div>
        </div>
        """
    html += """
    </div>
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        const sessions = document.querySelectorAll('.session');
        sessions.forEach((session, idx) => {
            session.querySelector('.toggle-btn').addEventListener('click', function() {
                const tracksDiv = document.getElementById('tracks-' + idx);
                if (!tracksDiv.dataset.loaded) {
                    fetch('/playlist_tracks/' + idx)
                        .then(resp => resp.text())
                        .then(html => {
                            tracksDiv.innerHTML = html;
                            tracksDiv.dataset.loaded = '1';
                        });
                }
            });
        });
    });
    </script>
    </body></html>"""
    # Guardar los ids de playlist en sesión para poder consultarlos por índice
    session['playlist_ids'] = [p['id'] for p in playlists]
    return html

@app.route('/playlist_tracks/<int:idx>')
def playlist_tracks(idx):
    token_info = session.get('token_info')
    if not token_info:
        return 'Not logged in', 401
    sp = Spotify(auth=token_info['access_token'])
    playlist_ids = session.get('playlist_ids', [])
    if idx >= len(playlist_ids):
        return 'Not found', 404
    playlist_id = playlist_ids[idx]
    tracks = []
    results = sp.playlist_tracks(playlist_id)
    while results:
        for item in results['items']:
            track = item['track']
            if track:
                name = track['name']
                artist = ', '.join([a['name'] for a in track['artists']])
                tracks.append(f"<li>{name} <span>by {artist}</span></li>")
        if results['next']:
            results = sp.next(results)
        else:
            results = None
    return f"<ul style='margin:0;padding-left:1em;'>{''.join(tracks)}</ul>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
