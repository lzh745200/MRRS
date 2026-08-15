import sqlite3
c = sqlite3.connect(r'data/smoke_test.db')
print("latest messages:")
for row in c.execute("SELECT id, user_id, message_type, title, is_read FROM messages ORDER BY id DESC LIMIT 10").fetchall():
    print(row)
print("count by user:", c.execute("SELECT user_id, COUNT(*) FROM messages GROUP BY user_id").fetchall())
