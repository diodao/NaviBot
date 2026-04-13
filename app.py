from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS
from functools import wraps
from rental_calculator import parse_request, calculate_rental
from database import (
    init_db, get_user_by_username, get_user_by_id, verify_password,
    get_all_users, create_user, update_user, delete_user, update_avatar,
    save_calculation, get_user_calculations, delete_calculation,
    get_all_boats, get_boat_by_id, get_boat_by_name, create_boat, update_boat, delete_boat,
    get_prices_for_boat, replace_prices_for_boat,
    get_boat_count, get_price_count, get_last_sync, log_sync,
    migrate_from_excel
)
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import jwt
import datetime
import logging
import os
import json
import uuid

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AVATARS_DIR = os.path.join(BASE_DIR, 'avatars')
os.makedirs(AVATARS_DIR, exist_ok=True)

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, 'frontend', 'dist'), static_url_path='')
CORS(app)

JWT_SECRET = os.environ.get('JWT_SECRET', 'navibot-dev-secret-change-me')
JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', '72'))


def create_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')


def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Требуется авторизация'}), 401
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            user = get_user_by_id(payload['user_id'])
            if not user:
                return jsonify({'error': 'Пользователь не найден'}), 401
            g.user = user
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Токен истёк'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Неверный токен'}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    @auth_required
    def decorated(*args, **kwargs):
        if g.user['role'] != 'admin':
            return jsonify({'error': 'Требуются права администратора'}), 403
        return f(*args, **kwargs)
    return decorated


def editor_required(f):
    """Доступ для admin и editor — редактирование теплоходов."""
    @wraps(f)
    @auth_required
    def decorated(*args, **kwargs):
        if g.user['role'] not in ('admin', 'editor'):
            return jsonify({'error': 'Требуются права редактора'}), 403
        return f(*args, **kwargs)
    return decorated


# === Auth ===

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Введите логин и пароль'}), 400

    user = get_user_by_username(username)
    if not user or not verify_password(password, user['password_hash']):
        return jsonify({'error': 'Неверный логин или пароль'}), 401

    token = create_token(user['id'])
    return jsonify({
        'token': token,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'display_name': user['display_name'],
            'role': user['role'],
            'avatar': user.get('avatar')
        }
    })


@app.route('/api/me', methods=['GET'])
@auth_required
def me():
    return jsonify({
        'user': {
            'id': g.user['id'],
            'username': g.user['username'],
            'display_name': g.user['display_name'],
            'role': g.user['role'],
            'avatar': g.user.get('avatar')
        }
    })


# === Calculate ===

@app.route('/api/calculate', methods=['POST'])
@auth_required
def calculate():
    data = request.get_json()
    text = data.get('text', '').strip()

    if not text:
        return jsonify({'error': 'Пустое сообщение.'}), 400

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return jsonify({'error': 'Пустое сообщение.'}), 400

    if len(lines) % 3 != 0:
        return jsonify({
            'error': 'Общее число непустых строк должно быть кратно 3 (дата, название, временной интервал для каждого запроса).'
        }), 400

    responses = []
    for i in range(0, len(lines), 3):
        block_lines = lines[i:i+3]
        block_text = "\n".join(block_lines)
        try:
            date_obj, boat_name, times = parse_request(block_text)
            result = calculate_rental(date_obj, boat_name, times)
            responses.append({'result': result})
        except Exception as e:
            logger.error("Ошибка при обработке блока: %s", e)
            responses.append({'error': f"Ошибка: {e}", 'input': block_text})

    save_calculation(g.user['id'], text, responses)
    return jsonify({'results': responses})


# === History ===

@app.route('/api/history', methods=['GET'])
@auth_required
def history():
    calcs = get_user_calculations(g.user['id'])
    result = []
    for c in calcs:
        result.append({
            'id': c['id'],
            'input_text': c['input_text'],
            'results': json.loads(c['results_json']),
            'created_at': c['created_at']
        })
    return jsonify({'history': result})


@app.route('/api/history/<int:calc_id>', methods=['DELETE'])
@auth_required
def delete_history_entry(calc_id):
    delete_calculation(calc_id, g.user['id'])
    return jsonify({'message': 'Удалено'})


# === Boats API ===

@app.route('/api/boats', methods=['GET'])
@auth_required
def list_boats():
    boats = get_all_boats()
    return jsonify({'boats': boats})


@app.route('/api/boats/<int:boat_id>', methods=['GET'])
@auth_required
def get_boat(boat_id):
    boat = get_boat_by_id(boat_id)
    if not boat:
        return jsonify({'error': 'Теплоход не найден'}), 404
    prices = get_prices_for_boat(boat_id)
    return jsonify({'boat': boat, 'prices': prices})


@app.route('/api/boats/<int:boat_id>', methods=['PUT'])
@editor_required
def edit_boat(boat_id):
    data = request.get_json()
    boat = get_boat_by_id(boat_id)
    if not boat:
        return jsonify({'error': 'Теплоход не найден'}), 404
    update_boat(boat_id, **data)
    return jsonify({'message': 'Теплоход обновлён'})


@app.route('/api/boats', methods=['POST'])
@admin_required
def add_boat():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Укажите название'}), 400
    boat_id = create_boat(
        name=name,
        link=data.get('link', ''),
        dock=data.get('dock', ''),
        cleaning_cost=data.get('cleaning_cost', 3000),
        prep_hours=data.get('prep_hours', 1.0),
        unload_hours=data.get('unload_hours', 0.5)
    )
    if not boat_id:
        return jsonify({'error': f'Теплоход "{name}" уже существует'}), 409
    return jsonify({'id': boat_id, 'message': f'Теплоход "{name}" добавлен'}), 201


@app.route('/api/boats/<int:boat_id>', methods=['DELETE'])
@admin_required
def remove_boat(boat_id):
    delete_boat(boat_id)
    return jsonify({'message': 'Теплоход удалён'})


# === Sync / Update ===

@app.route('/api/sync/status', methods=['GET'])
@auth_required
def sync_status():
    last = get_last_sync()
    return jsonify({
        'boats_count': get_boat_count(),
        'prices_count': get_price_count(),
        'last_sync': last
    })


@app.route('/api/sync/wp', methods=['POST'])
@editor_required
def sync_from_wp():
    """Синхронизация цен с WordPress через REST API (navibot/v1/prices)."""
    from wp_parser import parse_wp_boat

    WP_PRICES_URL = 'https://teplohod-restoran.ru/wp-json/navibot/v1/prices'

    try:
        import requests
        resp = requests.get(WP_PRICES_URL, timeout=60)
        resp.raise_for_status()
        wp_data = resp.json()

        updated = 0
        skipped = []
        for boat_data in wp_data.get('boats', []):
            boat_name = boat_data.get('name', '').strip()
            if not boat_name:
                continue

            boat = get_boat_by_name(boat_name)
            if not boat:
                # Автоматически создаём новый теплоход из WP
                new_id = create_boat(name=boat_name, wp_slug=boat_data.get('slug', ''))
                if new_id:
                    boat = get_boat_by_id(new_id)
                    logger.info("WP sync: создан новый теплоход '%s' (id=%d)", boat_name, new_id)
                else:
                    skipped.append(boat_name)
                    continue

            prices_list = parse_wp_boat(boat_data)
            if prices_list:
                replace_prices_for_boat(boat['id'], prices_list)
                updated += 1

        details = f'Обновлено: {updated}'
        if skipped:
            details += f', не найдено в БД: {len(skipped)} ({", ".join(skipped[:5])})'
        log_sync('wordpress', 'success', details)
        return jsonify({
            'message': f'Синхронизация завершена. Обновлено: {updated} теплоходов',
            'updated': updated,
            'skipped': skipped
        })

    except Exception as e:
        log_sync('wordpress', 'error', str(e))
        logger.error("Ошибка синхронизации с WP: %s", e)
        return jsonify({'error': f'Ошибка синхронизации: {e}'}), 500


@app.route('/api/sync/migrate-excel', methods=['POST'])
@admin_required
def migrate_excel():
    """Одноразовая миграция из Excel."""
    excel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rental_data.xlsx')
    if not os.path.exists(excel_path):
        return jsonify({'error': 'Файл rental_data.xlsx не найден'}), 404

    try:
        migrate_from_excel(excel_path)
        return jsonify({
            'message': 'Миграция из Excel завершена',
            'boats_count': get_boat_count(),
            'prices_count': get_price_count()
        })
    except Exception as e:
        logger.error("Ошибка миграции: %s", e)
        return jsonify({'error': f'Ошибка миграции: {e}'}), 500


# === Admin: Users ===

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_list_users():
    return jsonify({'users': get_all_users()})


@app.route('/api/admin/users', methods=['POST'])
@admin_required
def admin_create_user():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    display_name = data.get('display_name', '').strip()
    role = data.get('role', 'manager')

    if not username or not password or not display_name:
        return jsonify({'error': 'Заполните все поля'}), 400

    if role not in ('admin', 'editor', 'manager'):
        return jsonify({'error': 'Роль должна быть admin, editor или manager'}), 400

    user_id = create_user(username, password, display_name, role)
    if user_id is None:
        return jsonify({'error': f'Пользователь "{username}" уже существует'}), 409

    return jsonify({'id': user_id, 'message': f'Пользователь "{display_name}" создан'}), 201


@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@admin_required
def admin_update_user(user_id):
    data = request.get_json()
    display_name = data.get('display_name')
    password = data.get('password')
    role = data.get('role')

    if role and role not in ('admin', 'editor', 'manager'):
        return jsonify({'error': 'Роль должна быть admin, editor или manager'}), 400

    update_user(user_id, display_name=display_name, password=password, role=role)
    return jsonify({'message': 'Пользователь обновлён'})


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    if user_id == g.user['id']:
        return jsonify({'error': 'Нельзя удалить самого себя'}), 400
    delete_user(user_id)
    return jsonify({'message': 'Пользователь удалён'})


# === Avatars ===

@app.route('/api/avatars/<filename>', methods=['GET'])
def serve_avatar(filename):
    return send_from_directory(AVATARS_DIR, filename)


@app.route('/api/admin/users/<int:user_id>/avatar', methods=['POST'])
@admin_required
def upload_avatar(user_id):
    if 'avatar' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400

    file = request.files['avatar']
    if not file.filename:
        return jsonify({'error': 'Пустой файл'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ('png', 'jpg', 'jpeg', 'webp'):
        return jsonify({'error': 'Допустимые форматы: png, jpg, jpeg, webp'}), 400

    filename = f"{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(AVATARS_DIR, filename)

    user = get_user_by_id(user_id)
    if user and user.get('avatar'):
        old_path = os.path.join(AVATARS_DIR, user['avatar'])
        if os.path.exists(old_path):
            os.remove(old_path)

    file.save(filepath)
    update_avatar(user_id, filename)
    return jsonify({'avatar': filename, 'message': 'Аватар обновлён'})


@app.route('/api/admin/users/<int:user_id>/avatar', methods=['DELETE'])
@admin_required
def delete_avatar(user_id):
    user = get_user_by_id(user_id)
    if user and user.get('avatar'):
        old_path = os.path.join(AVATARS_DIR, user['avatar'])
        if os.path.exists(old_path):
            os.remove(old_path)
    update_avatar(user_id, None)
    return jsonify({'message': 'Аватар удалён'})


# === SPA fallback — отдаём index.html для всех не-API маршрутов ===

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_spa(path):
    # Если запрос к файлу который существует в dist/ — отдаём его
    dist_dir = app.static_folder
    if dist_dir and os.path.exists(os.path.join(dist_dir, path)):
        return send_from_directory(dist_dir, path)
    # Иначе — index.html (SPA routing)
    if dist_dir and os.path.exists(os.path.join(dist_dir, 'index.html')):
        return send_from_directory(dist_dir, 'index.html')
    return 'NaviBot API is running. Frontend not built.', 200


# === Init & Run ===

init_db()

# Автоматическая миграция из Excel если БД пуста
if get_boat_count() == 0:
    excel_path = os.path.join(BASE_DIR, 'rental_data.xlsx')
    if os.path.exists(excel_path):
        logger.info("БД пуста — запускаю миграцию из Excel...")
        migrate_from_excel(excel_path)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
