from docworker.analysis_app import create_app, get_db
from docworker import users


def test_user_lookup(app):
  with app.app_context():
    db = get_db()
    user_name = users.get_user_by_key(db, 'fookey1')
    assert user_name is not None
