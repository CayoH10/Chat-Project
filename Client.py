from socket import socket, AF_INET, SOCK_STREAM
import json


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
  
registrar_cliente()



