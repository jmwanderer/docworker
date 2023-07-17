from . import users
import unittest
import sqlite3
import pkg_resources

USER_NAME='test-user'
USER_KEY='test-key'

class UsersDBTestCase(unittest.TestCase):

  def setUp(self):
    schema_file = pkg_resources.resource_filename('docworker', 'schema.sql')  
    self.db = sqlite3.connect("testdb.sqlite",
                         detect_types=sqlite3.PARSE_DECLTYPES)
    self.db.row_factory = sqlite3.Row
    with open(schema_file, 'rb') as f:
      self.db.executescript(f.read().decode('utf8'))
  
  def testFunctions(self):
    # Add user
    users.add_or_update_user(self.db, USER_NAME, USER_NAME, 100)
    users.note_user_access(self.db, USER_NAME)
    users.add_or_update_user(self.db, USER_NAME, USER_NAME, 200)    

    # Verify access key functions
    key = users.get_user_key(self.db, USER_NAME)
    self.assertIsNotNone(key)
    user = users.get_user_by_key(self.db, key)
    self.assertIsNotNone(user)
    users.set_user_key(self.db, USER_NAME, USER_KEY)
    user = users.get_user_by_key(self.db, key)
    self.assertIsNone(user)
    user = users.get_user_by_key(self.db, USER_KEY)
    self.assertIsNotNone(user)    

    # Verify email functions
    self.assertTrue(users.check_allow_email_send(self.db, USER_NAME))
    users.note_email_send(self.db, USER_NAME)
    self.assertFalse(users.check_allow_email_send(self.db, USER_NAME))

    # Verify token functions
    self.assertEquals(users.token_count(self.db, USER_NAME), 200)
    users.increment_tokens(self.db, USER_NAME, 100)
    self.assertEquals(users.token_count(self.db, USER_NAME), 100)
    self.assertTrue(users.check_available_tokens(self.db, USER_NAME))
    users.increment_tokens(self.db, USER_NAME, 100)
    self.assertFalse(users.check_available_tokens(self.db, USER_NAME))    


