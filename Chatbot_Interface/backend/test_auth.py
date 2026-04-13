import sqlite3
import bcrypt

conn = sqlite3.connect('data/users.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()
row = c.execute("SELECT * FROM users WHERE username='Abhinav'").fetchone()

if row:
    print(f"User found: {dict(row)}")
    print(f"Password hash type: {type(row['password_hash'])}")
    print(f"Password hash length: {len(row['password_hash'])}")
    
    # Let's see if checkpw throws when using a generic password
    try:
        if bcrypt.checkpw(b"genericpassword", row['password_hash'].encode()):
            print("Password match!")
        else:
            print("Password NO match (expected format wise, but checking if checkpw crashes)")
    except Exception as e:
        print(f"EXCEPTION in bcrypt checkpw: {type(e).__name__} - {str(e)}")
else:
    print("User 'Abhinav' not found in users.db")
