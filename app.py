from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
CORS(app)

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

# Для хранения текущих звонков в памяти сервера (для простоты, лучше сделать через БД или кеш)
active_calls = {}

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


@app.route('/call', methods=['POST'])
def start_call():
    data = request.get_json()
    caller = data.get('from')
    callee = data.get('to')

    if not caller or not callee:
        return jsonify({"error": "Both 'from' and 'to' fields required"}), 400

    # Сохраняем активный звонок — кто звонит кому
    active_calls[callee] = caller
    return jsonify({"message": f"Calling {callee} from {caller}"}), 200


@app.route('/incoming-call', methods=['GET'])
def incoming_call():
    user = request.args.get('user')
    if not user:
        return jsonify({"error": "User query param required"}), 400

    caller = active_calls.get(user)
    if caller:
        return jsonify({"calling": True, "from": caller}), 200
    else:
        return jsonify({"calling": False}), 200


@app.route('/decline-call', methods=['POST'])
def decline_call():
    data = request.get_json()
    callee = data.get('user')
    if not callee:
        return jsonify({"error": "'user' field required"}), 400

    # Удаляем звонок при отклонении
    if callee in active_calls:
        del active_calls[callee]
    return jsonify({"message": "Call declined"}), 200


@app.route('/end-call', methods=['POST'])
def end_call():
    data = request.get_json()
    callee = data.get('user')
    if not callee:
        return jsonify({"error": "'user' field required"}), 400

    # Удаляем звонок при завершении
    if callee in active_calls:
        del active_calls[callee]
    return jsonify({"message": "Call ended"}), 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
