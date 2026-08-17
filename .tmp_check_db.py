
import sys
sys.path.insert(0, 'D:\\work\\exam-mistake-manager\\scripts')
from database import get_db_path, get_conn
print('DB path:', get_db_path())
with get_conn() as conn:
    rows = conn.execute('SELECT id, image_path FROM mistakes LIMIT 5').fetchall()
    for r in rows:
        print(r['id'], '->', r['image_path'])

