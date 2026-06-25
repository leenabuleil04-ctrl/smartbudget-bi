import os
import sys
from io import BytesIO
from dotenv import load_dotenv

# Ensure project root is on sys.path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

load_dotenv(os.path.join(ROOT, '.env'))
os.environ['FLASK_SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'testsecret')

from app import app


def run_test():
    client = app.test_client()

    # register a user
    resp = client.post('/register', data={'name': 'Test Student', 'email': 'test@example.com', 'password': 'pass'}, follow_redirects=True)
    assert resp.status_code == 200

    # login
    resp = client.post('/login', data={'email': 'test@example.com', 'password': 'pass'}, follow_redirects=True)
    assert resp.status_code == 200

    # upload CSV
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'samples', 'sample_transactions.csv')
    with open(csv_path, 'rb') as f:
        data = {'file': (BytesIO(f.read()), 'sample_transactions.csv')}
        resp = client.post('/import', data=data, content_type='multipart/form-data', follow_redirects=True)

    print('Import response status:', resp.status_code)
    body = resp.get_data(as_text=True)
    if 'Imported' in body:
        print('Import appears successful — dashboard should show metrics.')
    else:
        print('Import response body:')
        print(body)


if __name__ == '__main__':
    run_test()
