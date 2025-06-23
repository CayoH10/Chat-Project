import sqlite3
import hashlib

class GerenciadorUsuarios:
    def __init__(self, caminho_banco='usuarios.db'):
        self.caminho_banco = caminho_banco
        self.inicializar_banco()

    def inicializar_banco(self):
        conn = sqlite3.connect(self.caminho_banco)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                senha_hash TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

    def deletar_todos(self):
        conn = sqlite3.connect(self.caminho_banco)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM usuarios")
        conn.commit()
        conn.close()
        print("✅ Todos os usuários foram apagados do banco.")

if __name__ == "__main__":
    gerenciador = GerenciadorUsuarios()
    gerenciador.deletar_todos()
