CREATE TABLE orders (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  total_amount REAL,
  status TEXT,
  created_at TEXT
);

CREATE TABLE order_items (
  id TEXT PRIMARY KEY,
  order_id TEXT,
  sku TEXT,
  quantity INTEGER
);

-- Intentionally missing indexes on user_id, order_id, and created_at.
