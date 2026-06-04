import os, datetime, uuid, time, threading
import bcrypt

DATABASE_URL = os.getenv('DATABASE_URL', '')
USE_PG = DATABASE_URL.startswith('postgres')
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'military.db')

# ────────────────────────────────────────────────
#  Connection pool & retry
# ────────────────────────────────────────────────
_pool = None
_pool_lock = threading.Lock()
MAX_RETRIES = 3
RETRY_DELAY = 0.5  # seconds

if USE_PG:
    import psycopg2
    import psycopg2.pool

    from contextlib import contextmanager

    def _ensure_pool():
        global _pool
        if _pool is None:
            with _pool_lock:
                if _pool is None:
                    _pool = psycopg2.pool.ThreadedConnectionPool(1, 10, DATABASE_URL, sslmode='require')

    @contextmanager
    def _get_conn():
        _ensure_pool()
        conn = _pool.getconn()
        try:
            yield conn
        finally:
            _pool.putconn(conn)

    def db_get(q, p=()):
        q = q.replace('?', '%s')
        for attempt in range(MAX_RETRIES):
            try:
                with _get_conn() as conn:
                    c = conn.cursor()
                    c.execute(q, p)
                    return c.fetchall()
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise e
        return []

    def db_run(q, p=()):
        q = q.replace('?', '%s')
        for attempt in range(MAX_RETRIES):
            try:
                with _get_conn() as conn:
                    c = conn.cursor()
                    c.execute(q, p)
                    conn.commit()
                    return c.rowcount
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise e
        return 0

    def transaction(func):
        def wrapper(*args, **kwargs):
            with _get_conn() as conn:
                try:
                    c = conn.cursor()
                    result = func(c, *args, **kwargs)
                    conn.commit()
                    return result
                except Exception as e:
                    conn.rollback()
                    raise e
        return wrapper

else:
    import sqlite3

    _sqlite_local = threading.local()

    def _get_sqlite():
        if not hasattr(_sqlite_local, 'conn') or _sqlite_local.conn is None:
            _sqlite_local.conn = sqlite3.connect(DB, check_same_thread=False)
            _sqlite_local.conn.execute("PRAGMA journal_mode=WAL")
            _sqlite_local.conn.execute("PRAGMA busy_timeout=5000")
            _sqlite_local.conn.execute("PRAGMA foreign_keys=ON")
        return _sqlite_local.conn

    def db_get(q, p=()):
        for attempt in range(MAX_RETRIES):
            try:
                conn = _get_sqlite()
                c = conn.cursor()
                c.execute(q, p)
                return c.fetchall()
            except sqlite3.OperationalError as e:
                if 'database is locked' in str(e) and attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise e
        return []

    def db_run(q, p=()):
        for attempt in range(MAX_RETRIES):
            try:
                conn = _get_sqlite()
                c = conn.cursor()
                c.execute(q, p)
                conn.commit()
                return c.rowcount
            except sqlite3.OperationalError as e:
                if 'database is locked' in str(e) and attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise e
        return 0

# ────────────────────────────────────────────────
#  Validation helpers
# ────────────────────────────────────────────────
def validate_username(u):
    u = u.strip().lower()
    if len(u) < 3: return False, 'يوزر قصير جداً (3 أحرف كحد أدنى)'
    if not u.isalnum() and '_' not in u: return False, 'اليوزر: أحرف وأرقام و _ فقط'
    return True, u

def validate_password(p):
    if len(p) < 4: return False, 'كلمة المرور قصيرة جداً (4 أحرف كحد أدنى)'
    return True, p

def validate_full_name(n):
    n = n.strip()
    if len(n) < 3: return False, 'الاسم قصير جداً'
    return True, n

# ────────────────────────────────────────────────
#  Init
# ────────────────────────────────────────────────
def create_indexes():
    for q in [
        "CREATE INDEX IF NOT EXISTS idx_attendance_user_date ON attendance(user_id, timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(DATE(timestamp))",
        "CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read)",
        "CREATE INDEX IF NOT EXISTS idx_leaves_user_active ON leaves(user_id, is_active)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_user_active ON sessions(user_id, is_active)",
        "CREATE INDEX IF NOT EXISTS idx_audit_admin ON audit_log(admin_id)",
        "CREATE INDEX IF NOT EXISTS idx_leave_requests_user ON leave_requests(user_id)",
    ]:
        try: db_run(q)
        except: pass

def init_db():
    if USE_PG:
        with _get_conn() as conn:
            c = conn.cursor()
            c.execute("""CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,full_name TEXT NOT NULL,role TEXT DEFAULT 'employee',chat_id BIGINT,device_uid TEXT,is_blocked INTEGER DEFAULT 0,phone_number TEXT DEFAULT NULL,rank_title TEXT DEFAULT '',is_deleted INTEGER DEFAULT 0,avatar TEXT DEFAULT '',created_at TEXT DEFAULT '',updated_at TEXT DEFAULT '')""")
            c.execute("""CREATE TABLE IF NOT EXISTS attendance (id SERIAL PRIMARY KEY,user_id INTEGER NOT NULL,action TEXT NOT NULL,latitude DOUBLE PRECISION,longitude DOUBLE PRECISION,timestamp TEXT NOT NULL,note TEXT DEFAULT '')""")
            c.execute("""CREATE TABLE IF NOT EXISTS leaves (id SERIAL PRIMARY KEY,user_id INTEGER NOT NULL,start_time TEXT,end_time TEXT,duration_label TEXT,is_active INTEGER DEFAULT 1)""")
            c.execute("""CREATE TABLE IF NOT EXISTS leave_requests (id SERIAL PRIMARY KEY,user_id INTEGER NOT NULL,duration_label TEXT,hours_duration INTEGER,request_date TEXT,status TEXT DEFAULT 'PENDING')""")
            c.execute("""CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY,user_id INTEGER NOT NULL,content TEXT NOT NULL,is_read INTEGER DEFAULT 0,created_at TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS shifts (id SERIAL PRIMARY KEY,shift_date TEXT NOT NULL,current_duty TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS urgent_reports (id SERIAL PRIMARY KEY,sender_id INTEGER NOT NULL,report_text TEXT NOT NULL,reply_text TEXT,created_at TEXT NOT NULL,status TEXT DEFAULT 'OPEN')""")
            c.execute("""CREATE TABLE IF NOT EXISTS circulars (id SERIAL PRIMARY KEY,content TEXT NOT NULL,created_at TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS history_records (id SERIAL PRIMARY KEY,user_id INTEGER NOT NULL,note TEXT NOT NULL,created_at TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS security_alerts (id SERIAL PRIMARY KEY,user_id INTEGER,alert_type TEXT NOT NULL,detail TEXT,created_at TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS shifts_archive (id SERIAL PRIMARY KEY,shift_date TEXT,current_duty TEXT,username TEXT DEFAULT '',created_at TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY,value TEXT NOT NULL DEFAULT '')""")
            c.execute("""CREATE TABLE IF NOT EXISTS audit_log (id SERIAL PRIMARY KEY,admin_id INTEGER NOT NULL,action TEXT NOT NULL,target_id INTEGER,details TEXT,created_at TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS sessions (id SERIAL PRIMARY KEY,user_id INTEGER NOT NULL,session_id TEXT UNIQUE NOT NULL,ip_address TEXT DEFAULT '',user_agent TEXT DEFAULT '',browser TEXT DEFAULT '',os TEXT DEFAULT '',device_type TEXT DEFAULT '',created_at TEXT NOT NULL,last_activity TEXT NOT NULL,is_active INTEGER DEFAULT 1)""")
            c.execute("""CREATE TABLE IF NOT EXISTS attendance_errors (id SERIAL PRIMARY KEY,user_id INTEGER,error TEXT NOT NULL,latitude DOUBLE PRECISION,longitude DOUBLE PRECISION,created_at TEXT NOT NULL)""")
            conn.commit()
    else:
        conn = _get_sqlite()
        c = conn.cursor()
        c.executescript('''
            CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,full_name TEXT NOT NULL,role TEXT DEFAULT 'employee',chat_id INTEGER,device_uid TEXT,is_blocked INTEGER DEFAULT 0,phone_number TEXT DEFAULT NULL,rank_title TEXT DEFAULT '',is_deleted INTEGER DEFAULT 0,avatar TEXT DEFAULT '',created_at TEXT DEFAULT '',updated_at TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,action TEXT NOT NULL,latitude REAL,longitude REAL,timestamp TEXT NOT NULL,note TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS leaves (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,start_time TEXT,end_time TEXT,duration_label TEXT,is_active INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS leave_requests (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,duration_label TEXT,hours_duration INTEGER,request_date TEXT,status TEXT DEFAULT 'PENDING');
            CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,content TEXT NOT NULL,is_read INTEGER DEFAULT 0,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS shifts (id INTEGER PRIMARY KEY AUTOINCREMENT,shift_date TEXT NOT NULL,current_duty TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS urgent_reports (id INTEGER PRIMARY KEY AUTOINCREMENT,sender_id INTEGER NOT NULL,report_text TEXT NOT NULL,reply_text TEXT,created_at TEXT NOT NULL,status TEXT DEFAULT 'OPEN');
            CREATE TABLE IF NOT EXISTS circulars (id INTEGER PRIMARY KEY AUTOINCREMENT,content TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS history_records (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,note TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS security_alerts (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,alert_type TEXT NOT NULL,detail TEXT,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS shifts_archive (id INTEGER PRIMARY KEY AUTOINCREMENT,shift_date TEXT,current_duty TEXT,username TEXT DEFAULT '',created_at TEXT);
            CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY,value TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT,admin_id INTEGER NOT NULL,action TEXT NOT NULL,target_id INTEGER,details TEXT,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,session_id TEXT UNIQUE NOT NULL,ip_address TEXT DEFAULT '',user_agent TEXT DEFAULT '',browser TEXT DEFAULT '',os TEXT DEFAULT '',device_type TEXT DEFAULT '',created_at TEXT NOT NULL,last_activity TEXT NOT NULL,is_active INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS attendance_errors (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,error TEXT NOT NULL,latitude REAL,longitude REAL,created_at TEXT NOT NULL);
        ''')
        conn.commit()

# ────────────────────────────────────────────────
#  Cryptography
# ────────────────────────────────────────────────
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(stored, password):
    if stored.startswith('$2'):
        try: return bcrypt.checkpw(password.encode('utf-8'), stored.encode('utf-8'))
        except: return False
    return stored == password

# ────────────────────────────────────────────────
#  Time helpers
# ────────────────────────────────────────────────
def ksa():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=3)

def ksa_str():
    return ksa().strftime('%Y-%m-%d %H:%M:%S')

# ────────────────────────────────────────────────
#  Rank helpers
# ────────────────────────────────────────────────
RANKS_ORDER = ['جندي','جندي أول','عريف','وكيل رقيب','رقيب','رقيب أول','رئيس رقباء','ملازم','ملازم أول','نقيب','رائد','مقدم','عقيد','عميد','لواء','فريق','فريق أول']

def rank_index(r):
    r = (r or '').strip()
    try: return RANKS_ORDER.index(r)
    except: return -1

# ────────────────────────────────────────────────
#  Users
# ────────────────────────────────────────────────
def get_user(username):
    r = db_get("SELECT id,username,password,full_name,role,chat_id,device_uid,is_blocked,phone_number,rank_title,avatar,is_deleted,created_at,updated_at FROM users WHERE LOWER(TRIM(username))=?", (username.strip().lower(),))
    if r: return dict(zip(['id','username','password','full_name','role','chat_id','device_uid','is_blocked','phone_number','rank_title','avatar','is_deleted','created_at','updated_at'], r[0]))
    return None

def get_user_by_id(uid):
    r = db_get("SELECT id,username,password,full_name,role,chat_id,device_uid,is_blocked,phone_number,rank_title,avatar,is_deleted,created_at,updated_at FROM users WHERE id=?", (uid,))
    if r: return dict(zip(['id','username','password','full_name','role','chat_id','device_uid','is_blocked','phone_number','rank_title','avatar','is_deleted','created_at','updated_at'], r[0]))
    return None

def get_soldiers():
    rows = db_get("SELECT id,full_name,username,is_blocked,rank_title,phone_number FROM users WHERE role='employee' AND (is_deleted IS NULL OR is_deleted=0)")
    return sorted(rows, key=lambda x: (-rank_index(x[4]), x[1]))

def get_deleted_soldiers():
    rows = db_get("SELECT id,full_name,username,is_blocked,rank_title,phone_number FROM users WHERE role='employee' AND is_deleted=1")
    return sorted(rows, key=lambda x: (-rank_index(x[4]), x[1]))

def get_users_impact(user_ids):
    if not user_ids: return {}
    ph = ','.join(['?' for _ in user_ids])
    result = {uid: {'attendance':0,'leaves':0,'history':0,'notifications':0} for uid in user_ids}
    for uid, cnt in db_get(f"SELECT user_id, COUNT(*) FROM attendance WHERE user_id IN ({ph}) GROUP BY user_id", user_ids):
        if uid in result: result[uid]['attendance'] = cnt
    for uid, cnt in db_get(f"SELECT user_id, COUNT(*) FROM leaves WHERE user_id IN ({ph}) GROUP BY user_id", user_ids):
        if uid in result: result[uid]['leaves'] = cnt
    for uid, cnt in db_get(f"SELECT user_id, COUNT(*) FROM history_records WHERE user_id IN ({ph}) GROUP BY user_id", user_ids):
        if uid in result: result[uid]['history'] = cnt
    for uid, cnt in db_get(f"SELECT user_id, COUNT(*) FROM notifications WHERE user_id IN ({ph}) GROUP BY user_id", user_ids):
        if uid in result: result[uid]['notifications'] = cnt
    return result

def add_user(u, p, n, role='employee', rank='', phone=''):
    ok, uname = validate_username(u)
    if not ok: return False, uname
    ok, pwd = validate_password(p)
    if not ok: return False, pwd
    ok, name = validate_full_name(n)
    if not ok: return False, name
    try:
        pw = hash_password(p)
        now = ksa_str()
        db_run("INSERT INTO users (username,password,full_name,role,rank_title,phone_number,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
               (uname, pw, name, role, rank.strip(), phone.strip(), now, now))
        return True, "تمت الإضافة بنجاح"
    except Exception as e:
        err = str(e).lower()
        if 'duplicate' in err or 'unique' in err or 'already exists' in err:
            return False, "يوزر موجود مسبقاً"
        return False, f"خطأ في الحفظ: {str(e)[:80]}"

ALLOWED_USER_FIELDS = {'username','password','full_name','rank_title','phone_number'}
_FIELD_COL_MAP = {'username':'username','password':'password','full_name':'full_name','rank_title':'rank_title','phone_number':'phone_number'}

def update_user(uid, field, value):
    if field not in ALLOWED_USER_FIELDS: return False
    col = _FIELD_COL_MAP[field]
    if field == 'password':
        if not validate_password(value)[0]: return False
        value = hash_password(value)
    elif field == 'username':
        ok, msg = validate_username(value)
        if not ok: return False
        db_run(f"UPDATE users SET username=?,updated_at=? WHERE id=?", (msg, ksa_str(), uid))
        return True
    elif field == 'full_name':
        ok, msg = validate_full_name(value)
        if not ok: return False
        value = msg
    v = value.strip() if isinstance(value, str) else value
    db_run(f"UPDATE users SET {col}=?,updated_at=? WHERE id=?", (v, ksa_str(), uid))
    return True

def set_admin_phone(username, phone):
    db_run("UPDATE users SET phone_number=?,updated_at=? WHERE username=? AND role='admin'", (phone, ksa_str(), username))

def delete_user(uid):
    db_run("UPDATE users SET is_deleted=1,updated_at=? WHERE id=?", (ksa_str(), uid))

def restore_user(uid):
    db_run("UPDATE users SET is_deleted=0,updated_at=? WHERE id=?", (ksa_str(), uid))

def toggle_block(uid):
    u = get_user_by_id(uid)
    if not u: return None
    new = 0 if u['is_blocked'] else 1
    db_run("UPDATE users SET is_blocked=?,updated_at=? WHERE id=?", (new, ksa_str(), uid))
    return new

def add_device_uid(uid, device_id):
    cur = get_user_by_id(uid)
    if not cur: return
    devices = cur.get('device_uid') or ''
    devs = [d for d in devices.split(',') if d]
    for stored in devs:
        if stored == device_id: return
    if len(devs) >= 2: devs.pop(0)
    devs.append(device_id)
    db_run("UPDATE users SET device_uid=?,updated_at=? WHERE id=?", (','.join(devs), ksa_str(), uid))

def reset_device_uid(uid):
    db_run("UPDATE users SET device_uid='',updated_at=? WHERE id=?", (ksa_str(), uid))

def get_admin_ids():
    return db_get("SELECT id FROM users WHERE role='admin'")

def get_employee_chat_ids():
    return db_get("SELECT chat_id FROM users WHERE role='employee' AND chat_id IS NOT NULL AND is_blocked=0")

# ────────────────────────────────────────────────
#  Attendance
# ────────────────────────────────────────────────
def get_today_attendance(user_id):
    today = ksa().strftime('%Y-%m-%d')
    rows = db_get("SELECT action FROM attendance WHERE user_id=? AND DATE(timestamp)=?", (user_id, today))
    return [r[0] for r in rows]

def record_attendance(user_id, action, lat, lng, note=''):
    if lat is None or lng is None:
        return False, 'بيانات الموقع غير صالحة'
    today_acts = get_today_attendance(user_id)
    if action == 'check_in' and 'check_in' in today_acts:
        return False, 'تم تسجيل الحضور مسبقاً اليوم'
    if action == 'check_out' and 'check_out' in today_acts:
        return False, 'تم تسجيل الانصراف مسبقاً'
    if action == 'check_out' and 'check_in' not in today_acts:
        return False, 'لا يمكن الانصراف قبل تسجيل الحضور'
    try:
        db_run("INSERT INTO attendance (user_id,action,latitude,longitude,timestamp,note) VALUES (?,?,?,?,?,?)",
               (user_id, action, lat, lng, ksa_str(), note))
        return True, ''
    except Exception as e:
        return False, f'خطأ في الحفظ: {str(e)[:60]}'

def get_report(date_str):
    rows = db_get("SELECT user_id,action,timestamp,note,latitude,longitude FROM attendance WHERE DATE(timestamp)=?", (date_str,))
    amap = {}
    for uid,action,ts,note,lat,lng in rows:
        if uid not in amap: amap[uid] = {'check_in':None,'check_out':None,'note':'','loc':'','loc_out':''}
        t = ts.split(' ')[1][:5] if ' ' in ts else ts
        loc = f"{lat},{lng}" if lat and lng else ''
        if action=='check_in' and not amap[uid]['check_in']:
            amap[uid]['check_in'] = t; amap[uid]['note'] = note or ''; amap[uid]['loc'] = loc
        elif action=='check_out':
            amap[uid]['check_out'] = t; amap[uid]['loc_out'] = loc
    return amap

def get_dates():
    return [r[0] for r in db_get("SELECT DISTINCT DATE(timestamp) FROM attendance ORDER BY DATE(timestamp) DESC LIMIT 30")]

# ────────────────────────────────────────────────
#  System settings
# ────────────────────────────────────────────────
def get_setting(key, default=None):
    r = db_get("SELECT value FROM system_settings WHERE key=?", (key,))
    return r[0][0] if r else default

def set_setting(key, value):
    db_run("INSERT INTO system_settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", (key, value))

def init_settings():
    db_run("INSERT INTO system_settings (key,value) VALUES ('system_locked','0') ON CONFLICT(key) DO NOTHING")
    db_run("INSERT INTO system_settings (key,value) VALUES ('db_version','3') ON CONFLICT(key) DO NOTHING")
    db_run("INSERT INTO system_settings (key,value) VALUES ('allow_multi_session','0') ON CONFLICT(key) DO NOTHING")

# ────────────────────────────────────────────────
#  Leaves
# ────────────────────────────────────────────────
def get_leave(user_id):
    r = db_get("SELECT start_time,end_time,duration_label FROM leaves WHERE user_id=? AND is_active=1", (user_id,))
    if r:
        try:
            if ksa() > datetime.datetime.strptime(r[0][1], '%Y-%m-%d %H:%M'):
                db_run("UPDATE leaves SET is_active=0 WHERE user_id=?", (user_id,)); return None
            return {'start':r[0][0],'end':r[0][1],'label':r[0][2]}
        except: return None
    return None

def bulk_get_leaves(user_ids):
    if not user_ids: return {}
    ph = ','.join(['?' for _ in user_ids])
    rows = db_get(f"SELECT user_id,start_time,end_time,duration_label FROM leaves WHERE user_id IN ({ph}) AND is_active=1", user_ids)
    now = ksa(); result = {}
    for uid, st, et, label in rows:
        try:
            if now <= datetime.datetime.strptime(et, '%Y-%m-%d %H:%M'):
                result[uid] = {'start':st,'end':et,'label':label}
        except: pass
    return result

def get_active_leaves():
    rows = db_get("SELECT l.user_id,u.full_name,u.chat_id,l.end_time,l.duration_label FROM leaves l JOIN users u ON l.user_id=u.id WHERE l.is_active=1")
    now = ksa()
    return [r for r in rows if r[3] and now <= datetime.datetime.strptime(r[3],'%Y-%m-%d %H:%M')]

def set_leave(user_id, hours):
    std = ksa(); etd = std + datetime.timedelta(hours=hours)
    db_run("UPDATE leaves SET is_active=0 WHERE user_id=?", (user_id,))
    db_run("INSERT INTO leaves (user_id,start_time,end_time,duration_label) VALUES (?,?,?,?)",
           (user_id, std.strftime('%Y-%m-%d %H:%M'), etd.strftime('%Y-%m-%d %H:%M'), f"{hours} ساعة"))
    return std, etd

def revoke_leave(user_id):
    db_run("UPDATE leaves SET is_active=0 WHERE user_id=?", (user_id,))

def request_leave(user_id, hours):
    db_run("INSERT INTO leave_requests (user_id,duration_label,hours_duration,request_date) VALUES (?,?,?,?)",
           (user_id, f"{hours} ساعة", hours, ksa().strftime('%Y-%m-%d %H:%M')))

def get_pending_requests():
    return db_get("SELECT id,user_id,duration_label,hours_duration,request_date,status FROM leave_requests WHERE status='PENDING' ORDER BY id DESC")

def approve_leave_request(req_id):
    row = db_get("SELECT user_id, hours_duration FROM leave_requests WHERE id=?", (req_id,))
    if not row: return None
    uid, hours = row[0]
    db_run("UPDATE leave_requests SET status='APPROVED' WHERE id=?", (req_id,))
    set_leave(uid, hours)
    return uid, hours

def reject_leave_request(req_id):
    row = db_get("SELECT user_id FROM leave_requests WHERE id=?", (req_id,))
    if not row: return None
    db_run("UPDATE leave_requests SET status='REJECTED' WHERE id=?", (req_id,))
    return row[0][0]

# ────────────────────────────────────────────────
#  Notifications
# ────────────────────────────────────────────────
def push_notif(user_id, content):
    db_run("INSERT INTO notifications (user_id,content,created_at) VALUES (?,?,?)",
           (user_id, content, ksa_str()))

def get_unread(user_id):
    return db_get("SELECT id,content,created_at FROM notifications WHERE user_id=? AND is_read=0 ORDER BY id", (user_id,))

def mark_read(user_id, ids=None):
    if ids:
        ph = ','.join('?' * len(ids))
        db_run(f"UPDATE notifications SET is_read=1 WHERE user_id=? AND id IN ({ph})", (user_id, *ids))
    else:
        db_run("UPDATE notifications SET is_read=1 WHERE user_id=?", (user_id,))

def get_all_notifications(user_id):
    return db_get("SELECT id,content,created_at,is_read FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50", (user_id,))

def delete_unread_notifications(user_id):
    db_run("DELETE FROM notifications WHERE user_id=?", (user_id,))

def delete_read_notifications(user_id):
    db_run("DELETE FROM notifications WHERE user_id=? AND is_read=1", (user_id,))

# ────────────────────────────────────────────────
#  Shifts
# ────────────────────────────────────────────────
def get_today_shifts():
    dt = ksa().strftime('%Y-%m-%d')
    return db_get("SELECT id,current_duty FROM shifts WHERE shift_date=? ORDER BY id", (dt,))

def set_shift(duty):
    dt = ksa().strftime('%Y-%m-%d'); ts = ksa_str()
    db_run("INSERT INTO shifts (shift_date,current_duty) VALUES (?,?)", (dt, duty))
    rows = db_get("SELECT username FROM users WHERE full_name=?", (duty.split(' / ')[-1],))
    uname = rows[0][0] if rows else ''
    db_run("INSERT INTO shifts_archive (shift_date,current_duty,username,created_at) VALUES (?,?,?,?)", (dt, duty, uname, ts))

def delete_shift(sid):
    db_run("DELETE FROM shifts WHERE id=?", (sid,))

def get_shift_archive():
    return db_get("SELECT shift_date,current_duty,username,created_at FROM shifts_archive ORDER BY id DESC LIMIT 50")

# ────────────────────────────────────────────────
#  Security
# ────────────────────────────────────────────────
def get_security_alerts(limit=20):
    return db_get("SELECT sa.created_at,u.full_name,sa.alert_type,sa.detail FROM security_alerts sa LEFT JOIN users u ON sa.user_id=u.id ORDER BY sa.id DESC LIMIT ?", (limit,))

def add_security_alert(user_id, alert_type, detail):
    db_run("INSERT INTO security_alerts (user_id,alert_type,detail,created_at) VALUES (?,?,?,?)",
           (user_id, alert_type, detail, ksa_str()))

def get_history_records(user_id=None):
    if user_id:
        return db_get("SELECT id,note,created_at FROM history_records WHERE user_id=? ORDER BY id DESC", (user_id,))
    return db_get("SELECT hr.id,u.full_name,hr.note,hr.created_at FROM history_records hr JOIN users u ON hr.user_id=u.id ORDER BY hr.id DESC LIMIT 30")

def add_history(user_id, note):
    db_run("INSERT INTO history_records (user_id,note,created_at) VALUES (?,?,?)",
           (user_id, note, ksa().strftime('%Y-%m-%d %H:%M')))

def delete_history(hid):
    db_run("DELETE FROM history_records WHERE id=?", (hid,))

# ────────────────────────────────────────────────
#  Sessions
# ────────────────────────────────────────────────
def create_session(user_id, session_id, ip_address='', user_agent='', browser='', os='', device_type=''):
    now = ksa_str()
    db_run("INSERT INTO sessions (user_id,session_id,ip_address,user_agent,browser,os,device_type,created_at,last_activity) VALUES (?,?,?,?,?,?,?,?,?)",
           (user_id, session_id, ip_address, user_agent, browser, os, device_type, now, now))

def get_session(session_id):
    r = db_get("SELECT id,user_id,session_id,ip_address,user_agent,browser,os,device_type,created_at,last_activity,is_active FROM sessions WHERE session_id=?", (session_id,))
    if r:
        cols = ['id','user_id','session_id','ip_address','user_agent','browser','os','device_type','created_at','last_activity','is_active']
        return dict(zip(cols, r[0]))
    return None

def update_session_activity(session_id):
    db_run("UPDATE sessions SET last_activity=? WHERE session_id=?", (ksa_str(), session_id))

def terminate_session(session_id):
    db_run("UPDATE sessions SET is_active=0 WHERE session_id=?", (session_id,))

def terminate_all_user_sessions(user_id, keep_current=None):
    if keep_current:
        db_run("UPDATE sessions SET is_active=0 WHERE user_id=? AND session_id!=?", (user_id, keep_current))
    else:
        db_run("UPDATE sessions SET is_active=0 WHERE user_id=?", (user_id,))

def get_user_sessions(user_id):
    rows = db_get("SELECT id,user_id,session_id,ip_address,user_agent,browser,os,device_type,created_at,last_activity,is_active FROM sessions WHERE user_id=? ORDER BY id DESC", (user_id,))
    cols = ['id','user_id','session_id','ip_address','user_agent','browser','os','device_type','created_at','last_activity','is_active']
    return [dict(zip(cols, r)) for r in rows]

def get_all_sessions(limit=100):
    rows = db_get("SELECT s.id,s.user_id,u.full_name,u.rank_title,s.session_id,s.ip_address,s.user_agent,s.browser,s.os,s.device_type,s.created_at,s.last_activity,s.is_active FROM sessions s JOIN users u ON s.user_id=u.id ORDER BY s.last_activity DESC LIMIT ?", (limit,))
    cols = ['id','user_id','full_name','rank_title','session_id','ip_address','user_agent','browser','os','device_type','created_at','last_activity','is_active']
    return [dict(zip(cols, r)) for r in rows]

def get_active_session_count(user_id):
    r = db_get("SELECT COUNT(*) FROM sessions WHERE user_id=? AND is_active=1", (user_id,))
    return r[0][0] if r else 0

def parse_user_agent(ua):
    browser = 'غير معروف'
    os_name = 'غير معروف'
    device_type = 'غير معروف'
    ua_lower = (ua or '').lower()
    if 'chrome' in ua_lower and 'edg' not in ua_lower and 'opr' not in ua_lower:
        browser = 'Chrome'
    elif 'firefox' in ua_lower:
        browser = 'Firefox'
    elif 'safari' in ua_lower and 'chrome' not in ua_lower:
        browser = 'Safari'
    elif 'edg' in ua_lower:
        browser = 'Edge'
    elif 'opr' in ua_lower or 'opera' in ua_lower:
        browser = 'Opera'
    elif 'msie' in ua_lower or 'trident' in ua_lower:
        browser = 'Internet Explorer'
    if 'windows' in ua_lower:
        os_name = 'Windows'; device_type = 'كمبيوتر'
    elif 'mac os' in ua_lower or 'macintosh' in ua_lower:
        os_name = 'macOS'; device_type = 'كمبيوتر'
    elif 'linux' in ua_lower:
        os_name = 'Linux'; device_type = 'كمبيوتر'
    elif 'android' in ua_lower:
        os_name = 'Android'; device_type = 'جوال'
        if ua and ('tablet' in ua_lower or 'ipad' in ua_lower):
            device_type = 'جهاز لوحي'
    elif 'ios' in ua_lower or 'iphone' in ua_lower:
        os_name = 'iOS'; device_type = 'جوال'
    elif 'ipad' in ua_lower:
        os_name = 'iOS'; device_type = 'جهاز لوحي'
    return browser, os_name, device_type

def log_attendance_error(user_id, error_msg, lat=None, lng=None):
    db_run("INSERT INTO attendance_errors (user_id,error,latitude,longitude,created_at) VALUES (?,?,?,?,?)",
           (user_id, error_msg, lat, lng, ksa_str()))

def get_attendance_errors(limit=50):
    rows = db_get("SELECT ae.id,u.full_name,ae.error,ae.latitude,ae.longitude,ae.created_at FROM attendance_errors ae LEFT JOIN users u ON ae.user_id=u.id ORDER BY ae.id DESC LIMIT ?", (limit,))
    cols = ['id','full_name','error','latitude','longitude','created_at']
    return [dict(zip(cols, r)) for r in rows]

# ────────────────────────────────────────────────
#  Circulars
# ────────────────────────────────────────────────
def get_circular():
    r = db_get("SELECT content,created_at FROM circulars ORDER BY id DESC LIMIT 1")
    return r[0] if r else None

def set_circular(content):
    db_run("INSERT INTO circulars (content,created_at) VALUES (?,?)", (content, ksa_str()))

# ────────────────────────────────────────────────
#  Audit log
# ────────────────────────────────────────────────
def log_action(admin_id, action, target_id=None, details=''):
    db_run("INSERT INTO audit_log (admin_id,action,target_id,details,created_at) VALUES (?,?,?,?,?)",
           (admin_id, action, target_id, details, ksa_str()))

def get_audit_log(limit=50):
    return db_get("SELECT al.id,COALESCE(u.full_name,'[محذوف]'),al.action,al.target_id,al.details,al.created_at FROM audit_log al LEFT JOIN users u ON al.admin_id=u.id ORDER BY al.id DESC LIMIT ?", (limit,))

def clear_old_audit():
    db_run("DELETE FROM audit_log WHERE created_at < ?", ((ksa() - datetime.timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S'),))

# ────────────────────────────────────────────────
#  Reports (urgent)
# ────────────────────────────────────────────────
def get_open_reports():
    return db_get("SELECT id,sender_id,report_text,created_at FROM urgent_reports WHERE status='OPEN' ORDER BY id DESC")

def send_report(sender_id, text):
    db_run("INSERT INTO urgent_reports (sender_id,report_text,created_at) VALUES (?,?,?)",
           (sender_id, text, ksa().strftime('%Y-%m-%d %H:%M')))

def reply_report(rep_id, reply_text):
    db_run("UPDATE urgent_reports SET reply_text=?,status='RESOLVED' WHERE id=?", (reply_text, rep_id))
    rows = db_get("SELECT sender_id FROM urgent_reports WHERE id=?", (rep_id,))
    return rows[0][0] if rows else None
