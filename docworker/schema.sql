DROP TABLE IF EXISTS user;

CREATE TABLE user (
  username TEXT UNIQUE NOT NULL,
  consumed_tokens INTEGER DEFAULT 0,
  limit_tokens INTEGER,
  last_access INTEGER DEFAULT 0
);

  
