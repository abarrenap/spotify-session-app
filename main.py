import os
import datetime
from flask import Flask, redirect, request, session, jsonify, send_from_directory
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

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
        return jsonify({'error': 'No recent tracks found'})

    tracks = []
    for item in items:
        played_at = datetime.datetime.strptime(item['played_at'], "%Y-%m-%dT%H:%M:%S.%fZ")
        played_at = played_at.replace(tzinfo=datetime.timezone.utc)
        tracks.append((played_at, item['track']['name']))

    tracks.sort()
    session_tracks = [tracks[-1]]
    for i in range(len(tracks)-2, -1, -1):
        gap = (session_tracks[0][0] - tracks[i][0]).total_seconds()
        if gap <= 600:
            session_tracks.insert(0, tracks[i])
        else:
            break

    start = session_tracks[0][0].isoformat()
    end = session_tracks[-1][0].isoformat()
    duration = round((session_tracks[-1][0] - session_tracks[0][0]).total_seconds() / 60, 2)

    return jsonify({
        "songs_count": len(session_tracks),
        "start_time": start,
        "end_time": end,
        "total_duration_minutes": duration,
        "songs": [t[1] for t in session_tracks]
    })