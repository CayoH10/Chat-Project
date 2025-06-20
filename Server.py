from socket import socket, AF_INET, SOCK_STREAM
import threading 
import json
import sqlite3
import hashlib

def inicializar_banco():
    conn = sqlite3.connect('usuarios.db')
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


def registrar_usuario(username, senha):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()

    try:
        cursor.execute('INSERT INTO usuarios (username, senha_hash) VALUES (?, ?)', (username, senha_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def lidar_com_usuario(cliente_socket, endereco):
    print(f"Cliente conectado: {endereco}")

    try:
        dados = cliente_socket.recv(1024).decode('utf-8')
        print("📨 Dados recebidos:", repr(dados))

        requisicao = json.loads(dados)
        acao = requisicao.get("acao")
        print("🔍 Ação:", acao)

        if acao == "registrar":
            usuario = requisicao.get("username")
            senha = requisicao.get("senha")

            if registrar_usuario(usuario, senha):
                resposta = {"status": "ok", "mensagem": "Usuário registrado com sucesso!"}
            else:
                resposta = {"status": "erro", "mensagem": "Usuário já existe."}

            cliente_socket.send(json.dumps(resposta).encode('utf-8'))
            print("✅ Resposta enviada ao cliente.")

    except Exception as e:
        print(f"❌ Erro com cliente {endereco}: {e}")

    finally:
        cliente_socket.close()
        print(f"🔌 Conexão encerrada: {endereco}")

    

def iniciar_servidor():
    inicializar_banco()

server_socket = socket(AF_INET, SOCK_STREAM)
server_socket.bind(('127.0.0.1', 12345))
server_socket.listen()

print("Servidor ouvindo na porta 12345...")

while True:
    cliente_socket, endereco = server_socket.accept()
    thread = threading.Thread(target=lidar_com_usuario, args=(cliente_socket, endereco))
    thread.start()

    if __name__ == "__main__":
     iniciar_servidor()

