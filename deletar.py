import sqlite3

username = "Maria"

conn = sqlite3.connect("usuarios.db")
cursor = conn.cursor()

cursor.execute(
    "DELETE FROM usuarios WHERE username = ?",
    (username,)
)

conn.commit()

print(f"Usuário '{username}' deletado.")

conn.close()