DROP TABLE IF EXISTS users;
CREATE TABLE users (name TEXT, email TEXT, role TEXT);
INSERT INTO users VALUES
  ('alice', 'alice@lab.example', 'user'),
  ('bob', 'bob@lab.example', 'user'),
  ('root', 'root@lab.example', 'admin');
