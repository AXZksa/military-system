import os, datetime, uuid
import bcrypt

DATABASE_URL = os.getenv('DATABASE_URL', '')
USE_PG = DATABASE_URL.startswith('postgres')

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'military.db')

if USE_PG:
    import psycopg2
    import psycopg2.extras

    def db_get(q, p=()):
        q = q.replace('?', '%s')
        if 'DATE(timestamp)' in q and '::date' not in q:
            q = q.replace('DATE(timestamp)', 'DATE(timestamp)')
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        c = conn.cursor()
        c.execute(q, p)
        rows = c.fetchall()
        conn.close()
        return rows

    def db_run(q, p=()):
        q = q.replace('?', '%s')
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        c = conn.cursor()
        c.execute(q, p)
        conn.commit()
        n = c.rowcount
        conn.close()
        return n

    def init_db():
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          SERIAL PRIMARY KEY,
                username    TEXT UNIQUE NOT NULL,
                password    TEXT NOT NULL,
                full_name   TEXT NOT NULL,
                role        TEXT DEFAULT 'employee',
                chat_id     BIGINT,
                device_uid  TEXT,
                is_blocked  INTEGER DEFAULT 0,
                phone_number TEXT DEFAULT NULL,
                rank_title  TEXT DEFAULT ''
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id        SERIAL PRIMARY KEY,
                user_id   INTEGER NOT NULL,
                action    TEXT NOT NULL,
                latitude  DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                timestamp TEXT NOT NULL,
                note      TEXT DEFAULT ''
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS leaves (
                id             SERIAL PRIMARY KEY,
                user_id        INTEGER UNIQUE NOT NULL,
                start_time     TEXT,
                end_time       TEXT,
                duration_label TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS leave_requests (
                id             SERIAL PRIMARY KEY,
                user_id        INTEGER NOT NULL,
                duration_label TEXT,
                hours_duration INTEGER,
                request_date   TEXT,
                status         TEXT DEFAULT 'PENDING'
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL,
                content    TEXT NOT NULL,
                is_read    INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS shifts (
                id          SERIAL PRIMARY KEY,
                shift_date  TEXT NOT NULL,
                current_duty TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS urgent_reports (
                id          SERIAL PRIMARY KEY,
                sender_id   INTEGER NOT NULL,
                report_text TEXT NOT NULL,
                reply_text  TEXT,
                created_at  TEXT NOT NULL,
                status      TEXT DEFAULT 'OPEN'
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS circulars (
                id         SERIAL PRIMARY KEY,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS history_records (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL,
                note       TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS security_alerts (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER,
                alert_type TEXT NOT NULL,
                detail     TEXT,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS shifts_archive (
                id SERIAL PRIMARY KEY, shift_date TEXT, current_duty TEXT,
                username TEXT DEFAULT '', created_at TEXT)
        """)
        conn.commit(); conn.close()

    def hash_password(password):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(stored, password):
        if stored.startswith('$2'):
            try: return bcrypt.checkpw(password.encode('utf-8'), stored.encode('utf-8'))
            except: return False
        return stored == password

    def add_user(u, p, n, role='employee', rank='', phone=''):
        try:
            pw = hash_password(p)
            db_run("INSERT INTO users (username,password,full_name,role,rank_title,phone_number) VALUES (%s,%s,%s,%s,%s,%s)",
                   (u.strip().lower(), pw, n.strip(), role, rank.strip(), phone.strip()))
            return True, "تمت الإضافة بنجاح"
        except Exception as e:
            if 'duplicate' in str(e).lower():
                return False, "يوزر موجود مسبقاً"
            return False, str(e)

    def update_user(uid, field, value):
        if field in ('username','password','full_name','rank_title','phone_number'):
            if field == 'password':
                value = hash_password(value)
            elif field == 'username':
                try:
                    db_run("UPDATE users SET username=%s WHERE id=%s", (value.strip().lower(), uid))
                    return True
                except: return False
            v = value.strip() if isinstance(value, str) else value
            db_run(f"UPDATE users SET {field}=%s WHERE id=%s", (v, uid))
            return True
        return False

else:
    import sqlite3

    def db_get(q, p=()):
        conn = sqlite3.connect(DB); c = conn.cursor()
        c.execute(q, p); rows = c.fetchall(); conn.close(); return rows

    def db_run(q, p=()):
        conn = sqlite3.connect(DB); c = conn.cursor()
        c.execute(q, p); conn.commit(); n = c.rowcount; conn.close(); return n

    def init_db():
        conn = sqlite3.connect(DB); c = conn.cursor()
        c.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT UNIQUE NOT NULL,
                password    TEXT NOT NULL,
                full_name   TEXT NOT NULL,
                role        TEXT DEFAULT 'employee',
                chat_id     INTEGER,
                device_uid  TEXT,
                is_blocked  INTEGER DEFAULT 0,
            phone_number TEXT DEFAULT NULL,
            rank_title  TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            action    TEXT NOT NULL,
            latitude  REAL,
            longitude REAL,
            timestamp TEXT NOT NULL,
            note      TEXT DEFAULT ''
        );
            CREATE TABLE IF NOT EXISTS leaves (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER UNIQUE NOT NULL,
                start_time     TEXT,
                end_time       TEXT,
                duration_label TEXT
            );
            CREATE TABLE IF NOT EXISTS leave_requests (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL,
                duration_label TEXT,
                hours_duration INTEGER,
                request_date   TEXT,
                status         TEXT DEFAULT 'PENDING'
            );
            CREATE TABLE IF NOT EXISTS notifications (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                content    TEXT NOT NULL,
                is_read    INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS shifts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_date  TEXT NOT NULL,
                current_duty TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS urgent_reports (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id   INTEGER NOT NULL,
                report_text TEXT NOT NULL,
                reply_text  TEXT,
                created_at  TEXT NOT NULL,
                status      TEXT DEFAULT 'OPEN'
            );
            CREATE TABLE IF NOT EXISTS circulars (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS history_records (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                note       TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS security_alerts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER,
                alert_type TEXT NOT NULL,
                detail     TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS shifts_archive (
                id INTEGER PRIMARY KEY AUTOINCREMENT, shift_date TEXT, current_duty TEXT,
                username TEXT DEFAULT '', created_at TEXT);
        ''')
        conn.commit(); conn.close()

    def hash_password(password):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(stored, password):
        if stored.startswith('$2'):
            try: return bcrypt.checkpw(password.encode('utf-8'), stored.encode('utf-8'))
            except: return False
        return stored == password

    def add_user(u, p, n, role='employee', rank='', phone=''):
        try:
            pw = hash_password(p)
            db_run("INSERT INTO users (username,password,full_name,role,rank_title,phone_number) VALUES (?,?,?,?,?,?)",
                   (u.strip().lower(), pw, n.strip(), role, rank.strip(), phone.strip()))
            return True, "تمت الإضافة بنجاح"
        except sqlite3.IntegrityError:
            return False, "يوزر موجود مسبقاً"
        except Exception as e:
            return False, str(e)

    def update_user(uid, field, value):
        if field in ('username','password','full_name','rank_title','phone_number'):
            if field == 'password':
                value = hash_password(value)
            elif field == 'username':
                try:
                    db_run("UPDATE users SET username=? WHERE id=?", (value.strip().lower(), uid))
                    return True
                except: return False
            db_run(f"UPDATE users SET {field}=? WHERE id=?", (value.strip() if isinstance(value, str) else value, uid))
            return True
        return False

def ksa():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=3)

def ksa_str():
    return ksa().strftime('%Y-%m-%d %H:%M:%S')

RANKS_ORDER = ['جندي','جندي أول','عريف','وكيل رقيب','رقيب','رقيب أول',
    'رئيس رقباء','ملازم','ملازم أول','نقيب','رائد','مقدم',
    'عقيد','عميد','لواء','فريق','فريق أول']

def rank_index(r):
    r = (r or '').strip()
    try: return RANKS_ORDER.index(r)
    except: return -1

def get_user(username):
    r = db_get("SELECT id,username,password,full_name,role,chat_id,device_uid,is_blocked,phone_number,rank_title,avatar FROM users WHERE LOWER(TRIM(username))=?"
               , (username.strip().lower(),))
    if r: return dict(zip(['id','username','password','full_name','role','chat_id','device_uid','is_blocked','phone_number','rank_title','avatar'], r[0]))
    return None

def get_user_by_id(uid):
    r = db_get("SELECT id,username,password,full_name,role,chat_id,device_uid,is_blocked,phone_number,rank_title,avatar FROM users WHERE id=?", (uid,))
    if r: return dict(zip(['id','username','password','full_name','role','chat_id','device_uid','is_blocked','phone_number','rank_title','avatar'], r[0]))
    return None

def get_soldiers():
    rows = db_get("SELECT id,full_name,username,is_blocked,rank_title,phone_number FROM users WHERE role='employee' AND (is_deleted IS NULL OR is_deleted=0)")
    return sorted(rows, key=lambda x: (-rank_index(x[4]), x[1]))

def set_admin_phone(username, phone):
    db_run("UPDATE users SET phone_number=? WHERE username=? AND role='admin'", (phone, username))

def delete_user(uid):
    db_run("UPDATE users SET is_deleted=1 WHERE id=?", (uid,))

def restore_user(uid):
    db_run("UPDATE users SET is_deleted=0 WHERE id=?", (uid,))

def toggle_block(uid):
    u = get_user_by_id(uid)
    if not u: return None
    new = 0 if u['is_blocked'] else 1
    db_run("UPDATE users SET is_blocked=? WHERE id=?", (new, uid))
    return new

def add_device_uid(uid, device_id):
    cur = get_user_by_id(uid)
    devices = cur['device_uid'] or ''
    devs = [d for d in devices.split(',') if d]
    if device_id in devs:
        return
    if len(devs) >= 2:
        return
    devs.append(device_id)
    db_run("UPDATE users SET device_uid=? WHERE id=?", (','.join(devs), uid))

def reset_device_uid(uid):
    db_run("UPDATE users SET device_uid=? WHERE id=?", ('', uid))

# Attendance
def get_today_attendance(user_id):
    today = ksa().strftime('%Y-%m-%d')
    rows = db_get("SELECT action FROM attendance WHERE user_id=? AND DATE(timestamp)=?", (user_id, today))
    return [r[0] for r in rows]

def record_attendance(user_id, action, lat, lng, note=''):
    today_acts = get_today_attendance(user_id)
    if action == 'check_in' and 'check_in' in today_acts:
        return False, 'تم تسجيل الحضور مسبقاً اليوم'
    if action == 'check_out' and 'check_out' in today_acts:
        return False, 'تم تسجيل الانصراف مسبقاً'
    if action == 'check_out' and 'check_in' not in today_acts:
        return False, 'لا يمكن الانصراف قبل تسجيل الحضور'
    db_run("INSERT INTO attendance (user_id,action,latitude,longitude,timestamp,note) VALUES (?,?,?,?,?,?)",
           (user_id, action, lat, lng, ksa_str(), note))
    return True, ''

def get_report(date_str):
    rows = db_get("SELECT user_id,action,timestamp,note,latitude,longitude FROM attendance WHERE DATE(timestamp)=?", (date_str,))
    amap = {}
    for uid,action,ts,note,lat,lng in rows:
        if uid not in amap: amap[uid] = {'check_in':None,'check_out':None,'note':'','loc':'','loc_out':''}
        t = ts.split(' ')[1][:5]
        loc = f"{lat},{lng}" if lat and lng else ''
        if action=='check_in' and not amap[uid]['check_in']:
            amap[uid]['check_in'] = t; amap[uid]['note'] = note or ''; amap[uid]['loc'] = loc
        elif action=='check_out':
            amap[uid]['check_out'] = t; amap[uid]['loc_out'] = loc
    return amap

def get_dates():
    return [r[0] for r in db_get("SELECT DISTINCT DATE(timestamp) FROM attendance ORDER BY DATE(timestamp) DESC LIMIT 30")]

# Leaves
def get_leave(user_id):
    r = db_get("SELECT start_time,end_time,duration_label FROM leaves WHERE user_id=? AND is_active=1", (user_id,))
    if r:
        if ksa() > datetime.datetime.strptime(r[0][1], '%Y-%m-%d %H:%M'):
            db_run("UPDATE leaves SET is_active=0 WHERE user_id=?", (user_id,)); return None
        return {'start':r[0][0],'end':r[0][1],'label':r[0][2]}
    return None

def get_active_leaves():
    rows = db_get("SELECT l.user_id,u.full_name,u.chat_id,l.end_time,l.duration_label FROM leaves l JOIN users u ON l.user_id=u.id WHERE l.is_active=1")
    now  = ksa()
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

# Notifications
def push_notif(user_id, content):
    db_run("INSERT INTO notifications (user_id,content,created_at) VALUES (?,?,?)",
           (user_id, content, ksa().strftime('%Y-%m-%d %H:%M')))

def get_unread(user_id):
    return db_get("SELECT id,content,created_at FROM notifications WHERE user_id=? AND is_read=0 ORDER BY id", (user_id,))

def mark_read(user_id, ids=None):
    if ids:
        placeholders = ','.join('?' * len(ids))
        db_run(f"UPDATE notifications SET is_read=1 WHERE user_id=? AND id IN ({placeholders})", (user_id, *ids))
    else:
        db_run("UPDATE notifications SET is_read=1 WHERE user_id=?", (user_id,))

def get_all_notifications(user_id):
    return db_get("SELECT id,content,created_at,is_read FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50", (user_id,))

# Shifts
def get_today_shifts():
    dt = ksa().strftime('%Y-%m-%d')
    return db_get("SELECT id,current_duty FROM shifts WHERE shift_date=? ORDER BY id", (dt,))

def set_shift(duty):
    dt = ksa().strftime('%Y-%m-%d')
    ts = ksa_str()
    db_run("INSERT INTO shifts (shift_date,current_duty) VALUES (?,?)", (dt, duty))
    rows = db_get("SELECT username FROM users WHERE full_name=?", (duty.split(' / ')[-1],))
    uname = rows[0][0] if rows else ''
    db_run("INSERT INTO shifts_archive (shift_date,current_duty,username,created_at) VALUES (?,?,?,?)",
           (dt, duty, uname, ts))

def delete_shift(sid):
    db_run("DELETE FROM shifts WHERE id=?", (sid,))

def get_shift_archive():
    return db_get("SELECT shift_date,current_duty,username,created_at FROM shifts_archive ORDER BY id DESC LIMIT 50")

# Security
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

# Circulars
def get_circular():
    r = db_get("SELECT content,created_at FROM circulars ORDER BY id DESC LIMIT 1")
    return r[0] if r else None

def set_circular(content):
    db_run("INSERT INTO circulars (content,created_at) VALUES (?,?)", (content, ksa().strftime('%Y-%m-%d %H:%M')))

# Audit log
def log_action(admin_id, action, target_id=None, details=''):
    db_run("INSERT INTO audit_log (admin_id,action,target_id,details,created_at) VALUES (?,?,?,?,?)",
           (admin_id, action, target_id, details, ksa_str()))

def get_audit_log(limit=50):
    return db_get("SELECT al.id,u.full_name,al.action,al.target_id,al.details,al.created_at FROM audit_log al JOIN users u ON al.admin_id=u.id ORDER BY al.id DESC LIMIT ?", (limit,))

def clear_old_audit():
    db_run("DELETE FROM audit_log WHERE created_at < ?", ((ksa() - datetime.timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S'),))

def delete_unread_notifications(user_id):
    db_run("DELETE FROM notifications WHERE user_id=?", (user_id,))

def delete_read_notifications(user_id):
    db_run("DELETE FROM notifications WHERE user_id=? AND is_read=1", (user_id,))

# Reports
def get_open_reports():
    return db_get("SELECT id,sender_id,report_text,created_at FROM urgent_reports WHERE status='OPEN' ORDER BY id DESC")

def send_report(sender_id, text):
    db_run("INSERT INTO urgent_reports (sender_id,report_text,created_at) VALUES (?,?,?)",
           (sender_id, text, ksa().strftime('%Y-%m-%d %H:%M')))

def reply_report(rep_id, reply_text):
    db_run("UPDATE urgent_reports SET reply_text=?,status='RESOLVED' WHERE id=?", (reply_text, rep_id))
    rows = db_get("SELECT sender_id FROM urgent_reports WHERE id=?", (rep_id,))
    return rows[0][0] if rows else None

def get_employee_chat_ids():
    return db_get("SELECT chat_id FROM users WHERE role='employee' AND chat_id IS NOT NULL AND is_blocked=0")

def get_admin_ids():
    return db_get("SELECT id FROM users WHERE role='admin'")
