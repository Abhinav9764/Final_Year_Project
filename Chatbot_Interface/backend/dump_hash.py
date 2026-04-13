import sqlite3
import json

conn = sqlite3.connect('data/users.db')
c = conn.cursor()
row = c.execute("SELECT password_hash FROM users WHERE username='Abhinav'").fetchone()

with open('dump_hash.txt', 'w', encoding='utf-8') as f:
    f.write(row[0])
