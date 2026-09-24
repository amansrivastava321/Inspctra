CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email TEXT,
  password_hash TEXT,
  role TEXT
);

CREATE TABLE orders (
  id INTEGER PRIMARY KEY,
  user_id TEXT,
  amount REAL,
  created_at TEXT
);

-- Missing indexes for user_id and created_at are intentional.
