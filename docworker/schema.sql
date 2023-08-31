DROP TABLE IF EXISTS user;

CREATE TABLE user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  access_key TEXT UNIQUE NOT NULL,  
  initialized BOOLEAN DEFAULT FALSE,
  consumed_tokens INTEGER DEFAULT 0,
  limit_tokens INTEGER,
  last_access INTEGER DEFAULT 0,
  last_email INTEGER DEFAULT 0  
);

  
