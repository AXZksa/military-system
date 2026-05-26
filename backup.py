import os, json, base64, threading, time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

GH_TOKEN  = os.getenv('GH_TOKEN', '')
GH_REPO   = 'AXZksa/military-system'
BACKUP_PATH = 'backup.json'

TABLES_MAP = {
    'users': ('id','username','password','full_name','role','chat_id','device_uid','is_blocked','phone_number','rank_title'),
    'attendance': ('id','user_id','action','latitude','longitude','timestamp','note'),
    'leaves': ('id','user_id','start_time','end_time','duration_label'),
    'leave_requests': ('id','user_id','duration_label','hours_duration','request_date','status'),
    'notifications': ('id','user_id','content','is_read','created_at'),
    'shifts': ('id','shift_date','current_duty'),
    'urgent_reports': ('id','sender_id','report_text','reply_text','created_at','status'),
    'circulars': ('id','content','created_at'),
    'history_records': ('id','user_id','note','created_at'),
    'security_alerts': ('id','user_id','alert_type','detail','created_at'),
    'shifts_archive': ('id','shift_date','current_duty','username','created_at'),
}

def _gh_headers():
    return {
        'Authorization': f'token {GH_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'military-system',
    }

def _fetch_backup():
    url = f'https://api.github.com/repos/{GH_REPO}/contents/{BACKUP_PATH}'
    req = Request(url, headers=_gh_headers())
    try:
        resp = urlopen(req)
        data = json.loads(resp.read())
        raw = base64.b64decode(data['content']).decode('utf-8')
        return json.loads(raw), data.get('sha')
    except HTTPError as e:
        if e.code == 404: return None, None
        return None, None

def _push_backup(content, sha=None):
    url = f'https://api.github.com/repos/{GH_REPO}/contents/{BACKUP_PATH}'
    payload = {
        'message': f'auto backup {__import__("database").ksa_str()}',
        'content': base64.b64encode(content.encode('utf-8')).decode('utf-8'),
    }
    if sha: payload['sha'] = sha
    req = Request(url, data=json.dumps(payload).encode('utf-8'),
                  headers={**_gh_headers(), 'Content-Type': 'application/json'},
                  method='PUT')
    try:
        urlopen(req)
    except:
        pass

def export_all():
    from database import db_get, USE_PG
    out = {}
    for table, cols in TABLES_MAP.items():
        try:
            rows = db_get(f"SELECT * FROM {table}")
            out[table] = [dict(zip(cols, r)) for r in rows]
        except:
            out[table] = []
    return out

def import_all(data):
    from database import db_run, USE_PG
    for table, cols in TABLES_MAP.items():
        rows = data.get(table, [])
        for row in rows:
            try:
                vals = [row.get(c) for c in cols]
                ph = ','.join(['?' for _ in cols])
                cs = ','.join(cols)
                if USE_PG:
                    db_run(f"INSERT INTO {table} ({cs}) VALUES ({ph}) ON CONFLICT DO NOTHING", vals)
                else:
                    db_run(f"INSERT OR IGNORE INTO {table} ({cs}) VALUES ({ph})", vals)
            except:
                pass

def do_backup():
    if not GH_TOKEN: return
    try:
        data = export_all()
        content = json.dumps(data, ensure_ascii=False, default=str)
        existing, sha = _fetch_backup()
        _push_backup(content, sha)
    except:
        pass

def do_restore():
    from database import db_get
    if not GH_TOKEN: return
    users = db_get("SELECT COUNT(*) FROM users")
    if users and users[0][0] > 0: return
    data, _ = _fetch_backup()
    if data:
        import_all(data)

_started = False
def start_auto_backup():
    global _started
    if _started or not GH_TOKEN: return
    _started = True
    def loop():
        while True:
            time.sleep(300)
            do_backup()
    t = threading.Thread(target=loop, daemon=True)
    t.start()
