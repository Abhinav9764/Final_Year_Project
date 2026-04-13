import bcrypt

pass_hash = b"$2b$12$FsDEz7vafk9v86EU1PGfROQXbSfk6EChX/yd5XYNAtshpbAiT7ZKO"

try:
    if bcrypt.checkpw(b"genericpassword", pass_hash):
        print("OK match")
    else:
        print("OK NO match")
except Exception as e:
    print(f"Exception: {type(e).__name__} - {str(e)}")
