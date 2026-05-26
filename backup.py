import os, json, base64, threading, time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

GH_TOKEN  = os.getenv('GH_TOKEN', '')
GH_REPO   = 'AXZksa/military-system'
BACKUP_PATH = 'backup.json'
RAWBASE    = f'https://raw.githubusercontent.com/{GH_REPO}/main/{BACKUP_PATH}'
LOCAL      = os.path.join(os.path.dirname(os.path.abspath(__file__)), BACKUP_PATH)

TABLES_MAP = {
    'users': ('id','username','password','full_name','role','chat_id','device_uid','is_blocked','phone_number','rank_title','is_deleted','avatar','created_at','updated_at'),
    'attendance': ('id','user_id','action','latitude','longitude','timestamp','note'),
    'leaves': ('id','user_id','start_time','end_time','duration_label','is_active'),
    'leave_requests': ('id','user_id','duration_label','hours_duration','request_date','status'),
    'notifications': ('id','user_id','content','is_read','created_at'),
    'shifts': ('id','shift_date','current_duty'),
    'urgent_reports': ('id','sender_id','report_text','reply_text','created_at','status'),
    'circulars': ('id','content','created_at'),
    'history_records': ('id','user_id','note','created_at'),
    'security_alerts': ('id','user_id','alert_type','detail','created_at'),
    'shifts_archive': ('id','shift_date','current_duty','username','created_at'),
    'system_settings': ('key','value'),
    'audit_log': ('id','admin_id','action','target_id','details','created_at'),
    'sessions': ('id','user_id','session_id','ip_address','user_agent','browser','os','device_type','created_at','last_activity','is_active'),
    'attendance_errors': ('id','user_id','error','latitude','longitude','created_at'),
}

LOCK = threading.Lock()

def _gh_headers():
    return {'Authorization': f'token {GH_TOKEN}', 'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'military-system'}

def _fetch_api():
    if not GH_TOKEN: return None, None
    try:
        resp = urlopen(Request(f'https://api.github.com/repos/{GH_REPO}/contents/{BACKUP_PATH}', headers=_gh_headers()))
        data = json.loads(resp.read())
        return json.loads(base64.b64decode(data['content']).decode('utf-8')), data.get('sha')
    except HTTPError as e:
        if e.code == 404: return None, None
        return None, None

def _push_api(content, sha=None):
    if not GH_TOKEN: return False
    payload = {'message': f'auto backup {__import__("database").ksa_str()}', 'content': base64.b64encode(content.encode()).decode()}
    if sha: payload['sha'] = sha
    try:
        urlopen(Request(f'https://api.github.com/repos/{GH_REPO}/contents/{BACKUP_PATH}',
                       data=json.dumps(payload).encode(),
                       headers={**_gh_headers(), 'Content-Type': 'application/json'}, method='PUT'))
        return True
    except: return False

def _fetch_raw():
    try:
        resp = urlopen(Request(RAWBASE, headers={'User-Agent': 'military-system'}), timeout=10)
        return json.loads(resp.read())
    except: return None

def _fetch_local():
    try:
        with open(LOCAL, 'r', encoding='utf-8') as f: return json.load(f)
    except: return None

def _push_local(content):
    try:
        with open(LOCAL, 'w', encoding='utf-8') as f: f.write(content)
    except: pass

def export_all():
    from database import db_get
    out = {}
    for table, cols in TABLES_MAP.items():
        try:
            rows = db_get(f"SELECT * FROM {table}")
            out[table] = [dict(zip(cols, r)) for r in rows]
        except: out[table] = []
    return out

def import_all(data):
    from database import db_run, db_get
    for table, cols in TABLES_MAP.items():
        rows = data.get(table, [])
        if not rows: continue
        for row in rows:
            try:
                vals = [row.get(c) for c in cols]
                ph = ','.join(['?' for _ in cols])
                cs = ','.join(cols)
                db_run(f"INSERT OR IGNORE INTO {table} ({cs}) VALUES ({ph})", vals)
            except: pass

# ── Public API ──

def do_backup():
    with LOCK:
        try:
            data = export_all()
            content = json.dumps(data, ensure_ascii=False, default=str)
            if GH_TOKEN:
                existing, sha = _fetch_api() or (None, None)
                _push_api(content, sha)
            _push_local(content)
        except: pass

def do_restore():
    from database import db_get
    with LOCK:
        try:
            users = db_get("SELECT COUNT(*) FROM users")
            if users and users[0][0] > 5: return
        except: pass
    data = None
    if GH_TOKEN:
        d, _ = _fetch_api() or (None, None)
        data = d
    if not data: data = _fetch_raw()
    if not data: data = _fetch_local()
    if data: import_all(data)

_started = False
def start_auto_backup():
    global _started
    if _started: return
    _started = True
    def loop():
        while True:
            time.sleep(300)
            do_backup()
    t = threading.Thread(target=loop, daemon=True)
    t.start()
