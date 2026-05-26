import sqlite3, sys
try:
    conn = sqlite3.connect(r'C:\التحميل\code\cod\military.db')
    c = conn.cursor()
    for tbl in ['users','attendance','notifications','leaves','leave_requests','shifts','shifts_archive','urgent_reports','security_alerts','history_records','circulars']:
        try:
            c.execute(f'SELECT COUNT(*) FROM {tbl}')
            print(f'{tbl}: {c.fetchone()[0]}')
        except Exception as e:
            print(f'{tbl}: ERROR - {e}')
    conn.close()
except Exception as e:
    print(f'FATAL: {e}')
    sys.exit(1)
