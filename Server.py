from collections import defaultdict
from socket import socket, AF_INET, SOCK_STREAM
import threading 
import json
import sqlite3
import hashlib

usuarios_online = {}
mensagens_pendentes = defaultdict(list)
lock = threading.Lock()

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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            remetente TEXT NOT NULL,
            destinatario TEXT NOT NULL,
            mensagem TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            entregue INTEGER DEFAULT 0
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
        
        elif acao == "listar_contatos":
            conn = sqlite3.connect('usuarios.db')
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM usuarios")
            usuarios = [linha[0] for linha in cursor.fetchall()]
            conn.close()

            resposta = {"status": "ok", "usuarios": usuarios}
            cliente_socket.send(json.dumps(resposta).encode('utf-8'))
            print("Lista de contatos enviada ao cliente.")

        elif acao == "enviar_mensagem":
            remetente = requisicao.get("remetente")
            destinatario = requisicao.get("destinatario")
            texto = requisicao.get("mensagem")
            timestamp = requisicao.get("timestamp")

            if destinatario in usuarios_online:
                socket_dest = usuarios_online[destinatario]
                mensagem_entregue = {
                    "remetente": remetente,
                    "mensagem": texto,
                    "timestamp": timestamp
                }
                socket_dest.send(json.dumps(mensagem_entregue).encode('utf-8'))
                print(f"✉️ Mensagem enviada para {destinatario}")
            else:
                print(f"📥 {destinatario} está offline. Armazenando mensagem no banco.")
                conn = sqlite3.connect('usuarios.db')
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO mensagens (remetente, destinatario, mensagem, timestamp, entregue)
                    VALUES (?, ?, ?, ?, 0)
                ''', (remetente, destinatario, texto, timestamp))
                conn.commit()
                conn.close()

        elif acao == "login":
            usuario = requisicao.get("username")
            senha = requisicao.get("senha")

            if autenticar_usuario(usuario, senha):
                with lock:
                    usuarios_online[usuario] = cliente_socket

                resposta = {"status": "ok", "mensagem": "login bem sucedido."}
                cliente_socket.send(json.dumps(resposta).encode('utf-8'))
                print(f"Login bem sucedido para {usuario}.")


                conn = sqlite3.connect('usuarios.db')
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, remetente, mensagem, timestamp
                    FROM mensagens
                    WHERE destinatario = ? AND entregue = 0  
                ''', (usuario,))
                pendentes = cursor.fetchall()

                for msg in pendentes:
                    msg_id, remetente, texto, timestamp = msg
                    pacote = {
                        "remetente": remetente,
                        "mensagem": texto,
                        "timestamp": timestamp
                    }
                    cliente_socket.send(json.dumps(pacote).encode('utf-8'))

                    cursor.execute('UPDATE mensagens SET entregue = 1 WHERE id = ?', (msg_id,))

                conn.commit()
                conn.close()

                print(f"📨 {len(pendentes)} mensagens pendentes entregues para {usuario}")
       
                escutar_mensagens(cliente_socket, usuario)

       
    except Exception as e:
        print(f"❌ Erro com cliente {endereco}: {e}")

    finally:
        cliente_socket.close()
        print(f"🔌 Conexão encerrada: {endereco}")

def escutar_mensagens(cliente_socket, usuario):
    try:
        while True:
            dados = cliente_socket.recv(4096).decode('utf-8')
            if not dados:
                break

            requisicao = json.loads(dados)
            if requisicao.get("acao") == "enviar_mensagem":
                destino = requisicao.get("destinatario")

                with lock:
                    if destino in usuarios_online:
                        destino_socket = usuarios_online[destino]
                        destino_socket.send(json.dumps(requisicao).encode('utf-8'))
                        print(f" Mensagem de {usuario} para {destino} enviada em tempo real.")
                    else:
                        mensagens_pendentes[destino].append(requisicao)
                        print(f"{destino} offline. Mensagem armazenada.")

    except:
        print(f"Conexão perdida com {usuario}")
    finally:
        with lock:
            if usuario in usuarios_online:
                del usuarios_online[usuario]
        cliente_socket.close()
        print(f"🔌 Conexão encerrada: {usuario}")

def autenticar_usuario(usuario, senha):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()

    senha_hash = hashlib.sha256(senha.encode()).hexdigest()

    cursor.execute('SELECT * FROM usuarios WHERE username = ? AND senha_hash = ?', (usuario, senha_hash))
    resultado = cursor.fetchone()

    conn.close()
    return resultado is not None

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

