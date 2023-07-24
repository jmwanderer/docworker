import pytest
import os
import tempfile
import docworker.analysis_app

from docworker.analysis_app import create_app, init_db, get_db

with open(os.path.join(os.path.dirname(__file__), 'data.sql'), 'rb') as f:
  _data_sql = f.read().decode('utf8')

@pytest.fixture()
def app():
  db_fd, db_path = tempfile.mkstemp()
  
  app = create_app(fakeai=True)
  app.config.update({
    "TESTING": True,
    "DATABASE": db_path,
    })

  with app.app_context():
    init_db()
    get_db().executescript(_data_sql)

  yield app

  os.close(db_fd)
  os.unlink(db_path)

  
@pytest.fixture()
def client(app):
  return app.test_client()


@pytest.fixture()
def runner(app):
  return app.text_cli_runner()


class Auth:
  def __init__(self, client):
    self._client = client

  def login(self, key='fookey1'):
    return self._client.get('/?authkey=%s' % key)


@pytest.fixture()
def auth(client):
  return Auth(client)
