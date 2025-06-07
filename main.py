import os
import datetime
from flask import Flask, redirect, request, session, jsonify, send_from_directory, Response
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
import os

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get("FLASK_SECRET", "super_secret")


sp_oauth = SpotifyOAuth(
    client_id=os.environ["SPOTIPY_CLIENT_ID"],
    client_secret=os.environ["SPOTIPY_CLIENT_SECRET"],
    redirect_uri=os.environ["SPOTIPY_REDIRECT_URI"],
    scope="user-read-recently-played"
)

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
    for item in items:
        played_at = datetime.datetime.strptime(item['played_at'], "%Y-%m-%dT%H:%M:%S.%fZ")
        played_at = played_at.replace(tzinfo=datetime.timezone.utc)
        artist = ', '.join([a['name'] for a in item['track']['artists']])
        tracks.append((played_at, item['track']['name'], artist))

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
    duration = round((session_tracks[-1][0] - session_tracks[0][0]).total_seconds() / 60, 2)
    songs = [(t[1], t[2]) for t in session_tracks]

    # Build an HTML page with dark theme and artist name
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <title>Spotify Session</title>
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
            .summary {{
                background: #232323;
                border: 1px solid #1DB954;
                padding: 20px;
                margin-bottom: 30px;
                border-radius: 8px;
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
        </style>
    </head>
    <body>
        <h1>Spotify Listening Session</h1>
        <div class="summary">
            <p><strong>Session Start Time:</strong> {start}</p>
            <p><strong>Session End Time:</strong> {end}</p>
            <p><strong>Total Duration:</strong> {duration} minutes</p>
            <p><strong>Number of Songs Played:</strong> {len(songs)}</p>
        </div>
        <h2>Tracks Played</h2>
        <ul class="songs">
            {''.join(f'<li>{i+1}. {song} <span>by {artist}</span></li>' for i, (song, artist) in enumerate(songs))}
        </ul>
    </body>
    </html>
    """

    return Response(html, mimetype='text/html')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
