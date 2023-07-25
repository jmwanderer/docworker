from docworker.analysis_app import get_db
from docworker import users
import docworker

def test_login_get(client):
  response = client.get('/login')
  assert response.status_code == 200


def test_login_post(app, client, mocker):
  mocker.patch('docworker.analysis_app.analysis_util.send_email')

  with app.app_context():
    db = get_db()
    key = users.get_user_key(db, 'test3')
    assert key is  None
  
  response = client.post('/login',
                         data={'address': 'test3'}
                         )
  assert response.status_code == 302

  with app.app_context():
    db = get_db()
    key = users.get_user_key(db, 'test3')
    assert key is not None
    assert not users.check_allow_email_send(db, 'test3')

  response = client.post('/login',
                         data={'address': 'test3'}
                         )
  assert response.status_code == 302



