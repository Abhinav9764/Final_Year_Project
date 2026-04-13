import bcrypt
import sys

print(sys.executable)
pass_hash = b"$2b$12$FsD7c6/XG3jLMoSEzFI/ILe994NKVY9n1iXw5g.b7OQZ/5P6S2k8q"

try:
    bcrypt.checkpw("password".encode('utf-8'), pass_hash)
    print("Normal check OK")
except Exception as e:
    print("Normal exception:", e)

# What if password is 100 bytes?
try:
    bcrypt.checkpw(b"A" * 100, pass_hash)
    print("Long check OK")
except Exception as e:
    print("Long exception:", e)
