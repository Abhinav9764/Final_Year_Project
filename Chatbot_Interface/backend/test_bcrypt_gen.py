import bcrypt

new_hash = bcrypt.hashpw(b"testpass", bcrypt.gensalt())
print("Newly generated hash:", new_hash)
print("Type of newly generated hash:", type(new_hash))

db_hash_str = "$2b$12$FsD7c6/XG3jLMoSEzFI/ILe994NKVY9n1iXw5g.b7OQZ/5P6S2k8q"
print("Length of DB hash:", len(db_hash_str))

# Print byte by byte
print([chr(c) for c in new_hash])
