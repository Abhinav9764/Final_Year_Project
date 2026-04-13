import sqlite3
conn = sqlite3.connect('data/users.db')
c = conn.cursor()
row = c.execute("SELECT password_hash FROM users WHERE username='Abhinav'").fetchone()
hash_str = row[0]
print("Raw string:", repr(hash_str))
print("Bytes hex:", hash_str.encode('utf-8').hex())
print("Length:", len(hash_str))
