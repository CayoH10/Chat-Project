from datetime import datetime
from socket import socket, AF_INET, SOCK_STREAM, timeout
import json
import threading
from time import strftime

timer_digitacao = None

def registrar_cliente():
    print("Conectando ao servidor...")

    try:
        cliente_socket = socket(AF_INET, SOCK_STREAM)
        cliente_socket.connect(('127.0.0.1', 12345))
        print("Conectado ao servidor.")
    except ConnectionRefusedError:
        print("Conexão recusada.")
        return

  
    username = input("Digite seu nome de usuário para registro: ")
    senha = input("Digite sua senha: ")


    mensagem = {
        "acao": "registrar",
        "username": username,
        "senha": senha
    }

    
    cliente_socket.send(json.dumps(mensagem).encode('utf-8'))
    print("Dados de registro enviados ao servidor.")
    
    
    resposta = cliente_socket.recv(1024).decode('utf-8')
    resposta_json = json.loads(resposta)

    if resposta_json.get("status") == "ok":
        print("✅ Registro realizado com sucesso.")
    else:
        print("❌ Erro ao registrar:", resposta_json.get("mensagem"))

    cliente_socket.close()
  

def listar_contatos():
    cliente_socket = socket(AF_INET, SOCK_STREAM)
    cliente_socket.connect(('127.0.0.1', 12345))

    mensagem = {
        "acao": "listar_contatos"
    }
    cliente_socket.send(json.dumps(mensagem).encode('utf-8'))

    resposta = cliente_socket.recv(4096).decode('utf-8')
    resposta_json = json.loads(resposta)

    if resposta_json.get("status") == "ok":
        print("Lista de usuarios:")
        for usuario in resposta_json.get("usuarios", []):
            print("-", usuario)

    else:
        print("Erro ao buscar contatos.")

    cliente_socket.close()

listar_contatos()

def enviar_mensagens(sock, username):
    while True:
        destinatario = input("> Para: ")
        notificar_digitacao(sock, username, destinatario)
        texto = input("> Mensagem: ")

        pacote = {
            "acao": "enviar_mensagem",
            "remetente": username,
            "destinatario": destinatario,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mensagem": texto
        }

        sock.send(json.dumps(pacote).encode('utf-8'))

def iniciar_chat():
    sock = socket(AF_INET, SOCK_STREAM)
    sock.connect(('127.0.0.1', 12345))

    username = input("Usuario: ")
    senha = input("Senha: ")

    login_msg = {
        "acao": "login",
        "username": username,
        "senha": senha
    }

    sock.send(json.dumps(login_msg).encode('utf-8'))
    resposta = json.loads(sock.recv(1024).decode('utf-8'))

    if resposta.get("status") == "ok":
        print("✅ Login bem-sucedido. Aguardando mensagens...")

        sock.settimeout(1.0)  # espera por até 1 segundo por mensagens
        try:
            while True:
                dados = sock.recv(4096).decode('utf-8')
                if not dados:
                    break
                mensagem = json.loads(dados)
                remetente = mensagem.get("remetente")
                texto = mensagem.get("mensagem")
                timestamp = mensagem.get("timestamp")
                print(f"\n📨 Mensagem de {remetente} às {timestamp}: {texto}")
        except timeout:
            pass  # terminou o tempo de espera pelas mensagens pendentes
        finally:
            sock.settimeout(None)  # volta ao modo bloqueante

        thread_receber = threading.Thread(target=escutar_servidor, args=(sock,))
        thread_receber.daemon = True
        thread_receber.start()

        enviar_mensagens(sock, username)

    else:
        print("❌ Erro:", resposta.get("mensagem"))
        sock.close()

def escutar_servidor(sock):
    try:
        while True:
            dados = sock.recv(4096).decode('utf-8')
            if not dados:
                break

            mensagem = json.loads(dados)
            acao = mensagem.get("acao")

            if mensagem.get("acao") == "enviar_mensagem":
                remetente = mensagem.get("remetente")
                texto = mensagem.get("mensagem")
                print(f"\nMensagem de {remetente}: {texto}\n> ", end="")
            elif acao == "status_digitacao":
                usuario = mensagem.get("usuario")
                if mensagem.get("digitando"):
                    print(f"\n {usuario} está digitando...\n> ", end="")
                else:
                    print(f"\n {usuario} parou de digitar.\n> ", end="")
               
    except:
        print("Conexão com o servidor foi perdida.")
    finally:
        sock.close()

def notificar_digitacao(sock, remetente, destinatario):
    global timer_digitacao

    mensagem = {
        "acao": "digitando",
        "remetente": remetente,
        "destinatario": destinatario
    }
    sock.send(json.dumps(mensagem).encode('utf-8'))

    if timer_digitacao:
        timer_digitacao.cancel()

    timer_digitacao = threading.Timer(2.0, notificar_parou_digitar, args=(sock, remetente, destinatario))
    timer_digitacao.start()

def notificar_parou_digitar(sock, remetente, destinatario):
    mensagem = {
        "acao": "parou_digitacao",
        "remetente": remetente,
        "destinatario": destinatario
    }
    sock.send(json.dumps(mensagem).encode('utf-8'))

if __name__ == "__main__":
    print("Bem-vindo ao Chat!")
    print("1 - Registrar")
    print("2 - Entrar no chat")
    escolha = input("Escolha uma opção: ")

    if escolha == "1":
        registrar_cliente()
    elif escolha == "2":
        iniciar_chat()
    else:
        print("Opção inválida.")
