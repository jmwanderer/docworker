import os
import os.path
import sys
import shutil
import pkg_resources
import datetime
import docworker


def note_user_access(db, name):
  """
  Update last access time for the user.
  """
  now = datetime.datetime.now()
  
  db.execute("UPDATE user SET last_access = ? WHERE username = ?",
               (now.timestamp(), name))
  db.commit()
  

def increment_tokens(db, name, count):
  """
  Update the token count.
  """
  print("increment tokens for %s - %d" % (name, count))
  (tokens,) = db.execute("SELECT consumed_tokens FROM user WHERE username = ?",
                     (name,)).fetchone()
  tokens += count
  db.execute("UPDATE user SET consumed_tokens = ? WHERE username = ?",
               (tokens, name))
  db.commit()

def check_available_tokens(db, name):
  """
  Check if the consumed_tokens are less than the limit tokens
  """
  (consumed, limit) = db.execute(
    "SELECT consumed_tokens, limit_tokens FROM user WHERE username = ?",
    (name,)).fetchone()
  
  return consumed < limit
  
  
def add_or_update_user(db, user_dir, name, limit):
  """
  Add a user if it doesn't exist. Otherwise update the limit.
  """
  (count,) = db.execute("SELECT COUNT(*) FROM user WHERE username = ?",
                     (name,)).fetchone()
  print("count %d" % count)
  if count == 0:
    print("add user")
    db.execute("INSERT INTO user (username, limit_tokens) VALUES (?,?)",
               (name, limit))
    populate_samples(user_dir)
  else:
    print("update user")
    db.execute("UPDATE user SET limit_tokens = ? WHERE username = ?",
               (limit,name))
  db.commit()


def populate_samples(user_dir):
  """
  Copy sample docs into user dir.
  """
  print("user dir = %s" % user_dir)
  samples_dir = pkg_resources.resource_filename('docworker', 'samples')
  print("samples dir = %s" % samples_dir)  
  if not os.path.exists(samples_dir):
    print("%s not found" % samples_dir)

  if not os.path.exists(user_dir):    
    os.makedirs(user_dir)
  for filename in os.listdir(samples_dir):
    if filename.endswith(".daf"):
      shutil.copyfile(os.path.join(samples_dir, filename),
                      os.path.join(user_dir, filename))
  print("done")
  

def list_users(db):
  q = db.execute("SELECT id, username, consumed_tokens, limit_tokens, datetime(last_access, 'unixepoch') FROM user")
  for (id, user, consumed, limit, last_access) in q.fetchall():
    print("user: [%d] %s, limit: %d, consumed %d, last access: %s" %
          (id, user, limit, consumed, last_access))
