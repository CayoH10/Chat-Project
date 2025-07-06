from collections import defaultdict
from socket import socket, AF_INET, SOCK_STREAM
import threading 
import json
import sqlite3
import hashlib
from datetime import datetime

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
        return {"status": "ok", "mensagem": "Usuário registrado com sucesso!"}
    except sqlite3.IntegrityError:
        return {"status": "erro", "mensagem": "Usuário já existe."}
    except Exception as e:
        return {"status": "erro", "mensagem": f"Erro inesperado: {e}"}
    finally:
        conn.close()

def lidar_com_usuario(cliente_socket, endereco):
    print(f"Cliente conectado: {endereco}")
    acao = None

    try:
        dados = cliente_socket.recv(1024).decode('utf-8')
        print("Dados recebidos:", repr(dados))
        if not dados.strip():
            raise ValueError("Dados recebidos vazios.")

        requisicao = json.loads(dados)
        acao = requisicao.get("acao")
        print("Ação:", acao)

        if acao == "registrar":
            usuario = requisicao.get("username")
            senha = requisicao.get("senha")
            resposta = registrar_usuario(usuario, senha)
            cliente_socket.send((json.dumps(resposta) + '\n').encode('utf-8'))
            print("Resposta enviada ao cliente.")
        
        elif acao == "listar_contatos":
            conn = sqlite3.connect('usuarios.db')
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM usuarios")
            usuarios = [linha[0] for linha in cursor.fetchall()]
            conn.close()

            resposta = {"status": "ok", "usuarios": usuarios}
            usuarios_status = []
            with lock:
                for u in usuarios:
                    status = "online" if u in usuarios_online else "offline"
                    usuarios_status.append({"nome": u, "status": status})

            resposta = {"status": "ok", "usuarios": usuarios_status}
            cliente_socket.send((json.dumps(resposta) + '\n').encode('utf-8'))
            cliente_socket.send((json.dumps(resposta) + '\n').encode('utf-8'))
            print(f"[DEBUG - SERVIDOR] Pedido de listar_contatos recebido de {endereco}")
            cliente_socket.close()

        elif acao == "enviar_mensagem":
            remetente = requisicao.get("remetente")
            destinatario = requisicao.get("destinatario")
            texto = requisicao.get("mensagem")
            timestamp = requisicao.get("timestamp")

            if destinatario in usuarios_online:
                try:
                    socket_dest = usuarios_online[destinatario]
                    mensagem_entregue = {
                        "acao": "enviar_mensagem",
                        "remetente": remetente,
                        "mensagem": texto,
                        "timestamp": timestamp
                    }
                    socket_dest.send((json.dumps(mensagem_entregue) + "\n").encode('utf-8'))
                    print(f"✉️ Mensagem enviada para {destinatario}")
                except Exception as e:
                    print(f"Erro ao entregar mensagem para {destinatario}. Salvando no banco. Erro: {e}")
                    salvar_mensagem_offline(remetente, destinatario, texto, timestamp)
            else:
                print(f"{destinatario} está offline. Armazenando mensagem no banco.")
                salvar_mensagem_offline(remetente, destinatario, texto, timestamp)

        elif acao == "login":
            usuario = requisicao.get("username")
            senha = requisicao.get("senha")

            if autenticar_usuario(usuario, senha):
                with lock:
                    usuarios_online[usuario] = cliente_socket

                resposta = {"status": "ok", "mensagem": "login bem sucedido."}
                cliente_socket.send((json.dumps(resposta) + '\n').encode('utf-8'))
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
                        "acao": "enviar_mensagem",
                        "remetente": remetente,
                        "mensagem": texto,
                        "timestamp": timestamp
                    }
                    cliente_socket.send((json.dumps(pacote) + '\n').encode('utf-8'))

                    cursor.execute('DELETE FROM mensagens WHERE id = ?', (msg_id,))

                conn.commit()
                conn.close()

                print(f"{len(pendentes)} mensagens pendentes entregues para {usuario}")
       
                escutar_mensagens(cliente_socket, usuario)

        elif acao == "digitando":
            tratar_digitando(requisicao)

        elif acao == "parou_digitacao":
            tratar_parar_digitacao(requisicao)

       
    except Exception as e:
        print(f"Erro com cliente {endereco}: {e}")

    finally:
        if acao not in ["login"]:
            cliente_socket.close()
            print(f"Conexão encerrada: {endereco}")

def escutar_mensagens(cliente_socket, usuario):
    buffer = ""
    try:
        while True:
            dados = cliente_socket.recv(4096).decode('utf-8')
            if not dados:
                break
            buffer += dados
            while '\n' in buffer:
                linha, buffer = buffer.split('\n', 1)
                if linha.strip() == "":
                    continue

            requisicao = json.loads(dados)
            acao = requisicao.get("acao")
            if requisicao.get("acao") == "enviar_mensagem":
                destino = requisicao.get("destinatario")

                with lock:
           
                    if destino in usuarios_online:
                        destino_socket = usuarios_online[destino]
                        destino_socket.send((json.dumps(requisicao) + '\n').encode('utf-8'))
                        print(f" Mensagem de {usuario} para {destino} enviada em tempo real.")
                    else:
                        salvar_mensagem_offline(
                        remetente=requisicao.get("remetente"),
                        destinatario=destino,
                        texto=requisicao.get("mensagem"),
                        timestamp=requisicao.get("timestamp")
                        )
                        print(f"{destino} offline. Mensagem salva no banco.")

            elif acao == "digitando":
               tratar_digitando(requisicao)

            elif acao == "parou_digitacao":
                tratar_parar_digitacao(requisicao)

    except:
        print(f"Conexão perdida com {usuario}")
    finally:
        with lock:
            if usuario in usuarios_online:
                del usuarios_online[usuario]
        cliente_socket.close()
        print(f"Conexão encerrada: {usuario}")

def salvar_mensagem_offline(remetente, destinatario, texto, timestamp):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO mensagens (remetente, destinatario, mensagem, timestamp, entregue)
        VALUES (?, ?, ?, ?, 0)
    ''', (remetente, destinatario, texto, timestamp))
    conn.commit()
    conn.close()

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

def tratar_digitando(requisicao):
    destinatario = requisicao.get("destinatario")
    remetente = requisicao.get("remetente")
    with lock:
        if destinatario in usuarios_online:
            socket_dest = usuarios_online[destinatario]
            status = {
                "acao": "status_digitacao",
                "usuario": remetente,
                "digitando": True
            }
            socket_dest.send((json.dumps(status) + '\n').encode('utf-8'))
            print(f"{remetente} está digitando para {destinatario}")

def tratar_parar_digitacao(requisicao):
    destinatario = requisicao.get("destinatario")
    remetente = requisicao.get("remetente")
    with lock:
        if destinatario in usuarios_online:
            socket_dest = usuarios_online[destinatario]
            status = {
                "acao": "status_digitacao",
                "usuario": remetente,
                "digitando": False
            }
            socket_dest.send((json.dumps(status) + '\n').encode('utf-8'))
            print(f"{remetente} parou de digitar para {destinatario}")
    

while True:
    cliente_socket, endereco = server_socket.accept()
    thread = threading.Thread(target=lidar_com_usuario, args=(cliente_socket, endereco))
    thread.start()

    if __name__ == "__main__":
     iniciar_servidor()

