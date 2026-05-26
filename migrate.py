"""
هذا السكربت ينقل البيانات من SQLite (قاعدة البيانات المحلية) إلى PostgreSQL (Supabase).
شغله بعد ما تسوي Supabase Database وتضبط DATABASE_URL.

الاستخدام:
  set DATABASE_URL=postgresql://...  (او حطها في ملف .env)
  python migrate.py
"""
import os, sys, sqlite3, psycopg2
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', '')
if not DATABASE_URL.startswith('postgres'):
    print('خطأ: لازم تحط DATABASE_URL في متغيرات البيئة')
    sys.exit(1)

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'military.db')
if not os.path.exists(DB):
    print(f'ما لقيت ملف SQLite: {DB}')
    sys.exit(1)

# اقرأ من SQLite
sq = sqlite3.connect(DB)
sq.row_factory = sqlite3.Row

# اكتب لـ PostgreSQL
pg = psycopg2.connect(DATABASE_URL, sslmode='require')
pgc = pg.cursor()

TABLES = [
    'users', 'attendance', 'leaves', 'leave_requests', 'notifications',
    'shifts', 'urgent_reports', 'circulars', 'history_records',
    'security_alerts', 'shifts_archive'
]

for table in TABLES:
    rows = sq.execute(f"SELECT * FROM {table}").fetchall()
    if not rows:
        print(f'{table}: 0 سجلات (تخطي)')
        continue
    cols = [d[0] for d in sq.execute(f"PRAGMA table_info({table})").fetchall()]
    placeholders = ','.join(['%s'] * len(cols))
    cols_str = ','.join(cols)
    inserted = 0
    for row in rows:
        vals = [row[c] for c in cols]
        try:
            pgc.execute(f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING", vals)
            inserted += 1
        except Exception as e:
            print(f'  خطأ في {table}: {e}')
    pg.commit()
    print(f'{table}: {inserted}/{len(rows)} سجل')

sq.close()
pg.close()
print('\nتم الترحيل بنجاح ✅')
