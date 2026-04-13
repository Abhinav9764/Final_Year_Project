import bcrypt
import sqlite3

conn = sqlite3.connect('data/users.db')
c = conn.cursor()

new_pw = "Abhinav123"
new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()

c.execute("UPDATE users SET password_hash = ? WHERE username = 'Abhinav'", (new_hash,))
conn.commit()

print("Password for Abhinav successfully reset.")
