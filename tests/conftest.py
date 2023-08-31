import pytest
import os
import tempfile
import docworker.analysis_app
from docworker.analysis_app import create_app, init_db, get_db
from docworker import users

@pytest.fixture()
def app():
  instance_path = tempfile.TemporaryDirectory()  
  
  app = create_app(fakeai=True, instance_path=instance_path.name)
  app.config.update({
    "TESTING": True,
    })

  with app.app_context():
    init_db()
    name = 'test1'
    users.add_or_update_user(get_db(), app.instance_path, name, 10)
    name = 'test2'
    users.add_or_update_user(get_db(), app.instance_path, name, 10)

  yield app

  instance_path.cleanup()

  
@pytest.fixture()
def client(app):
  return app.test_client()


@pytest.fixture()
def runner(app):
  return app.text_cli_runner()


class Auth:
  def __init__(self, app, client):
    self._app = app
    self._client = client

  def login(self, user):
    with self._app.app_context():
      db = get_db()
      key = users.get_user_key(db, user)
      return self._client.get('/login?authkey=%s' % key)


@pytest.fixture()
def auth(app, client):
  return Auth(app, client)
