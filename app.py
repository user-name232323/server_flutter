from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from flask_socketio import SocketIO, emit

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Конфигурация базы (замени на свои реальные данные)
DB_CONFIG = {
    "host": "dpg-d604jmkoud1c7391ugb0-a.oregon-postgres.render.com",
    "port": 5432,
    "database": "call_app_66x2",
    "user": "call_user",
    "password": "6BrrsH4nPmbUq3jWmatBzmTRvP0v5h8A"
}

def get_db_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    return conn

connected_users = {}  # username -> sid

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": "Username already exists"}), 409
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": str(e)}), 500

    cur.close()
    conn.close()
    return jsonify({"message": "User registered successfully"}), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        return jsonify({"error": "User not found"}), 404

    if user["password"] != password:
        return jsonify({"error": "Invalid password"}), 401

    return jsonify({"message": "Login successful"}), 200


@app.route('/users', methods=['GET'])
def get_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()
    users_list = [{"id": user[0], "username": user[1]} for user in users]
    return jsonify(users_list), 200


# --- WebSocket handlers ---

@socketio.on('connect')
def on_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    disconnected_user = None
    for user, sid in connected_users.items():
        if sid == request.sid:
            disconnected_user = user
            break
    if disconnected_user:
        del connected_users[disconnected_user]
        print(f"User disconnected: {disconnected_user}")
    print(f"Client disconnected: {request.sid}")

@socketio.on('register_user')
def on_register_user(data):
    username = data.get('username')
    if username:
        connected_users[username] = request.sid
        print(f"User registered to socket: {username}")

@socketio.on('call_user')
def on_call_user(data):
    callee = data.get('callee')
    caller = data.get('caller')
    sid = connected_users.get(callee)
    if sid:
        emit('incoming_call', {'from': caller}, room=sid)

@socketio.on('answer_call')
def on_answer_call(data):
    caller = data.get('caller')
    callee = data.get('callee')
    sid = connected_users.get(caller)
    if sid:
        emit('call_answered', {'from': callee}, room=sid)

@socketio.on('ice_candidate')
def on_ice_candidate(data):
    target = data.get('target')
    candidate = data.get('candidate')
    sid = connected_users.get(target)
    if sid:
        emit('ice_candidate', {'candidate': candidate}, room=sid)

@socketio.on('sdp_offer')
def on_sdp_offer(data):
    target = data.get('target')
    sdp = data.get('sdp')
    sid = connected_users.get(target)
    if sid:
        emit('sdp_offer', {'sdp': sdp}, room=sid)

@socketio.on('sdp_answer')
def on_sdp_answer(data):
    target = data.get('target')
    sdp = data.get('sdp')
    sid = connected_users.get(target)
    if sid:
        emit('sdp_answer', {'sdp': sdp}, room=sid)


if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
