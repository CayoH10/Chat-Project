import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext
from datetime import datetime, time
from Security import proteger_socket_cliente
import socket
import json
import threading
import time
import os
import base64

from Security import (
    gerar_chaves_dh,
    serializar_chave_publica,
    carregar_chave_publica,
    derivar_chave_sessao
)

timer_digitacao = None
sock = None
usuario = ""
destinatario_atual = ""
contatos_disponiveis = []
conversas = {}
estado_troca_chaves = {}
chaves_sessao = {}

def registrar_gui():
    username = entry_novo_usuario.get()
    senha = entry_nova_senha.get()

    if not username or not senha:
        messagebox.showwarning("Campos vazios", "Preencha todos os campos.")
        return
    cliente_socket = None

    try:
        cliente_socket = conectar_servidor()

        mensagem = {
            "acao": "registrar",
            "username": username,
            "senha": senha
        }

        cliente_socket.sendall((json.dumps(mensagem) + '\n').encode('utf-8'))
        dados = b""

        while b'\n' not in dados:
            parte = cliente_socket.recv(4096)

            if not parte:
                raise ConnectionError("O servidor encerrou a conexão")
            dados += parte

        linha,_ = dados.split(b'\n', 1)
        resposta_json = json.loads(linha.decode('utf-8'))

        if resposta_json.get("status") == "ok":
            messagebox.showinfo("Sucesso", "Registro realizado com sucesso.")
            frame_registro.pack_forget()
            frame_login.pack()
        else:
            messagebox.showerror("Erro", f"Erro ao registrar: {resposta_json.get('mensagem')}")

    except Exception as e:
        messagebox.showerror("Erro", f"Falha na conexão com servidor.\n{e}")

    finally:
        if cliente_socket:
            cliente_socket.close()

def conectar_servidor():
    cliente_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cliente_socket.connect(('127.0.0.1', 12345))
    try:
        cliente_seguro = proteger_socket_cliente(cliente_socket)
        return cliente_seguro
    except Exception:
        cliente_socket.close()
        raise

def enviar_json(dado):
    global sock

    if sock is None:
        raise ConnectionError("Não há conexão com o servidor.")
    
    mensagem = json.dumps(dado) + '\n'
    sock.sendall(mensagem.encode('utf-8'))

def tentar_reconectar():
    global sock, buffer

    try:
        print("[INFO] Tentando reconectar...")

        novo_socket = conectar_servidor()

        login_msg = {
            "acao": "login",
            "username": usuario,
            "senha": entry_senha.get()
        }

        novo_socket.sendall((json.dumps(login_msg) + '\n').encode('utf-8'))

        dados = b""

        while b'\n' not in dados:
            parte = novo_socket.recv(4096)

            if not parte:
                raise ConnectionError("Servidor encerrou a conexão.")
            dados += parte
        linha, restante = dados.split(b'\n', 1)
        resposta = json.loads(linha.decode('utf-8'))

        if resposta.get("status") == "ok":
            sock = novo_socket
            buffer = restante.decode('utf-8')
            print("[INFO] Reconectado com sucesso.")
        else:
            novo_socket.close()
            print("[ERRO] Falha ao reconectar:", resposta.get("mensagem"))

    except Exception as e:
        print(f"[ERRO] Não foi possivel reconectar: {e}")

def receber_mensagens():
    global sock, buffer

    while True:
        try:
            dados = sock.recv(4096)

            if not dados:
                raise ConnectionError("Servidor encerrou a conexão.")

            buffer += dados.decode('utf-8')

            while '\n' in buffer:
                linha, buffer = buffer.split('\n', 1)

                if not linha.strip():
                    continue

                try:
                    mensagem = json.loads(linha)
                    acao = mensagem.get("acao")

                    if acao == "enviar_mensagem":
                        remetente = mensagem["remetente"]
                        texto = mensagem["mensagem"]
                        timestamp = mensagem["timestamp"]

                        if remetente not in conversas:
                            conversas[remetente] = []

                        conversas[remetente].append((remetente, texto, timestamp))

                        if remetente == destinatario_atual:
                            root.after(0, mostrar_conversa, destinatario_atual)
                    elif acao == "status_digitacao":
                        status = (
                            f"{mensagem['usuario']} esta digitando..."
                            if mensagem['digitando']
                            else ""
                        )

                        root.after(0, lambda s=status: label_status.config(text=s))

                    else:
                        print(f"[WARN] Ação desconhecida: {acao}")
                except json.JSONDecodeError as e:
                    print(f"[ERRO] JSON inválido: {e}")
        except Exception as e:
            print(f"[ERRO] Conexão perdida: {e}")

            atualizar_status_conexao("Conexão perdida. Tentando reconectar...", "red")
            root.after(0, lambda: messagebox.showwarning("Conexão perdida", "Tentando reconectar ao servidor..."))
            tentar_reconectar()
            break
        
def mostrar_mensagem(texto):
    chat_area.config(state='normal')
    chat_area.insert(tk.END, texto + "\n")
    chat_area.config(state='disabled')
    chat_area.see(tk.END)

def ao_digitar(event):
    global timer_digitacao

    if not destinatario_atual or sock is None:
        return
    
    enviar_json({
        "acao": "digitando",
        "remetente": usuario,
        "destinatario": destinatario_atual
    })

    if timer_digitacao:
        timer_digitacao.cancel()

    timer_digitacao = threading.Timer(2.0, notificar_parou_digitar, args=(sock, usuario, destinatario_atual))
    timer_digitacao.start()
  

def listar_contatos():
    cliente_socket = None

    try:
        cliente_socket = conectar_servidor()

        mensagem = {"acao": "listar_contatos"}
        cliente_socket.sendall((json.dumps(mensagem) + '\n').encode('utf-8'))

        dados = b""
        while b'\n' not in dados:
            parte = cliente_socket.recv(4096)
            
            if not parte:
                raise ConnectionError("O servidor encerrou a conexão.")
            dados += parte

        linha, _ = dados.split(b'\n', 1)
        return json.loads(linha.decode('utf-8'))

    except Exception as e:
        print(f"[ERRO] Falha ao listar contatos: {e}")

        return {
            "status": "erro",
            "mensagem": "Erro ao listar contatos."
        }
    finally:
        if cliente_socket:
            cliente_socket.close()
    
    
def carregar_contatos():
    global contatos_disponiveis
    resposta = listar_contatos()
    if resposta.get("status") == "ok":
        contatos_disponiveis = [
            contato for contato in resposta.get("usuarios")
            if contato["nome"] != usuario
        ]
        lista_contatos.delete(0, tk.END)
        for contato in contatos_disponiveis:
            nome = contato["nome"]
            status = contato["status"]
            icone = "Online" if status == "online" else "Offline"

            lista_contatos.insert(
                tk.END,
                f"{nome} - {icone}"
            )

    else:
        messagebox.showerror(
            "Erro",
            resposta.get("mensagem")
        )

def atualizar_contatos():
    carregar_contatos()
    root.after(3000, atualizar_contatos)

def enviar_mensagens():
    global timer_digitacao

    texto = entry_mensagem.get()
    if not texto.strip():
        return

    if not destinatario_atual:
        messagebox.showwarning(
            "Aviso",
            "Selecione um contato primeiro"
        )
        return
    
    pacote = {
        "acao": "enviar_mensagem",
        "remetente": usuario,
        "destinatario": destinatario_atual,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mensagem": texto
    }
    enviar_json(pacote)
    if destinatario_atual not in conversas:
        conversas[destinatario_atual] = []
    conversas[destinatario_atual].append(("Você", texto, pacote["timestamp"]))

    mostrar_conversa(destinatario_atual)
    entry_mensagem.delete(0, tk.END)

    if timer_digitacao:
        timer_digitacao.cancel()
        timer_digitacao = None

    notificar_parou_digitar(sock, usuario, destinatario_atual)

root = tk.Tk()
root.title("Chat App")
root.geometry("300x250")

# Tela Inicial
frame_inicio = tk.Frame(root)
frame_inicio.pack()

def mostrar_login():
    frame_inicio.pack_forget()
    frame_login.pack()

def mostrar_registro():
    frame_inicio.pack_forget()
    frame_registro.pack()

btn_login = tk.Button(frame_inicio, text="Entrar", width=20, command=mostrar_login)
btn_login.pack(pady=10)

btn_registrar = tk.Button(frame_inicio, text="Registrar conta", width=20, command=mostrar_registro)
btn_registrar.pack(pady=10)

def atualizar_status_conexao(msg, cor="gray"):
    label_status.config(text=msg, fg=cor)
    if cor == "green":
        label_status.after(5000, lambda: label_status.config(text=""))

def iniciar_chat():
    global usuario, destinatario_atual, sock

    usuario = entry_usuario.get()
    senha = entry_senha.get()

    if not usuario or not senha:
        messagebox.showwarning("Campos vazios", "Preencha usuário e senha.")
        return
    
    try:
        sock = conectar_servidor()
        login_msg = {
            "acao": "login",
            "username": usuario,
            "senha": senha
        }
        sock.sendall((json.dumps(login_msg) + '\n').encode('utf-8'))

        dados = b""

        while b'\n' not in dados:
            parte = sock.recv(4096)

            if not parte:
                raise ConnectionError("O servidor encerrou a conexão.")

            dados += parte

        linha, restante = dados.split(b'\n', 1)
        resposta = json.loads(linha.decode('utf-8'))

        if resposta.get("status") == "ok":
            buffer = restante.decode('utf-8')

            messagebox.showinfo("Sucesso", "Login realizado com sucesso.")

            frame_login.pack_forget()
            frame_chat.pack()

            threading.Thread(target=receber_mensagens, daemon=True).start()
            carregar_contatos()
            atualizar_contatos()

            root.after(1000, atualizar_contatos_periodicamente)

        else:
            messagebox.showerror("Erro", resposta.get("Mensagem", "Falha no login"))
            sock.close()
            sock = None
    except Exception as e:
        if sock:
            sock.close()
            sock = None
        messagebox.showerror("Erro", f"Erro ao conectar ao servidor: {e}")


def fazer_login(sock, username, senha):
    login_msg = {
        "acao": "login",
        "username": username,
        "senha": senha
    }
    sock.send(json.dumps(login_msg).encode('utf-8'))
    resposta = json.loads(sock.recv(1024).decode('utf-8'))
    return resposta

def receber_mensagens_pendentes(sock):
    mensagens = []
    sock.settimeout(1.0)
    try:
        while True:
            dados = sock.recv(4096).decode('utf-8')
            if not dados:
                break
            mensagem = json.loads(dados)
            mensagens.append(mensagem)
    except socket.timeout:
        pass
    finally:
        sock.settimeout(None)

    return mensagens

def escutar_servidor(sock, atualizar_interface):
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
       atualizar_interface("Conexão com servidor perdida.")
    finally:
        sock.close()
    

def selecionar_contato(event):
    global destinatario_atual
    indice = lista_contatos.curselection()
    if indice:
        contato = contatos_disponiveis[indice[0]]
        destinatario_atual = contato["nome"]
        label_status.config(text=f"Conversando com: {destinatario_atual}")
        mostrar_conversa(destinatario_atual)

lista_contatos = tk.Listbox(root, height=10)
lista_contatos.pack(padx=10, pady=10)
lista_contatos.bind("<<ListboxSelect>>", selecionar_contato)

def mostrar_conversa(contato):
    chat_area.config(state=tk.NORMAL)
    chat_area.delete("1.0", tk.END)
    mensagens = conversas.get(contato, [])

    for remetente, mensagem, timestamp in mensagens:
        chat_area.insert(tk.END, f"{remetente}: {mensagem}\n")
    chat_area.config(state=tk.DISABLED)

def notificar_digitacao(sock, remetente, destinatario):
    if sock is None:
        return

    mensagem = {
        "acao": "digitando",
        "remetente": remetente,
        "destinatario": destinatario
    }

    sock.sendall((json.dumps(mensagem) + '\n').encode('utf-8'))

def notificar_parou_digitar(sock, remetente, destinatario):
    if sock is None:
        return

    mensagem = {
        "acao": "parou_digitacao",
        "remetente": remetente,
        "destinatario": destinatario
    }

    sock.sendall((json.dumps(mensagem) + '\n').encode('utf-8'))

def atualizar_contatos_periodicamente():
    carregar_contatos()
    root.after(5000, atualizar_contatos_periodicamente)

def iniciar_troca_chaves():
    if not destinatario_atual:
        return

    chave_privada, chave_publica = gerar_chaves_dh()

    chave_publica_bytes = serializar_chave_publica(chave_publica)
    salt = os.urandom(16)

    estado_troca_chaves[destinatario_atual] = {
        "chave_privada": chave_privada,
        "salt": salt
    }

    pacote = {
        "acao": "trocar_chave",
        "remetente": usuario,
        "destinatario": destinatario_atual,
        "chave_publica": base64.b64encode(
            chave_publica_bytes
        ).decode("utf-8"),
        "salt": base64.b64encode(salt).decode("utf-8")
    }

    enviar_json(pacote)

def responder_troca_chaves(requisicao):
    remetente = requisicao.get("remetente")
    chave_publica_remota = requisicao.get("chave_publica") 
    salt_recebido = requisicao.get("salt")

    if not remetente or not chave_publica_remota or not salt_recebido:
        print("[ERRO] Solicitação de troca de chaves incompleta")
        return

    chave_privada, chave_publica = gerar_chaves_dh()

    chave_bytes = base64.b64decode(chave_publica_remota)
    chave_publica_remota = carregar_chave_publica(chave_bytes)
    salt = base64.b64decode(salt_recebido)

    chaves_sessao = derivar_chave_sessao(
        chave_privada,
        chave_publica_remota,
        salt
    )

    chaves_sessao[remetente] = chaves_sessao

    pacote = {
        "acao": "resposta_chave",
        "remetente": usuario,
        "destinatario": remetente,
        "chave_publica": base64.b64encode(serializar_chave_publica(chave_publica)).decode('utf-8'),
        "salt": salt_recebido
    }

# Tela de Login
frame_login = tk.Frame(root)

tk.Label(frame_login, text="Usuário:").pack()
entry_usuario = tk.Entry(frame_login)
entry_usuario.pack()

tk.Label(frame_login, text="Senha:").pack()
entry_senha = tk.Entry(frame_login, show="*")
entry_senha.pack()

btn_entrar_chat = tk.Button(frame_login, text="Entrar no chat", command=iniciar_chat)  
btn_entrar_chat.pack(pady=10)


frame_registro = tk.Frame(root)

tk.Label(frame_registro, text="Novo usuário:").pack()
entry_novo_usuario = tk.Entry(frame_registro)
entry_novo_usuario.pack()

tk.Label(frame_registro, text="Nova senha:").pack()
entry_nova_senha = tk.Entry(frame_registro, show="*")
entry_nova_senha.pack()

btn_finalizar_registro = tk.Button(frame_registro, text="Registrar", command=registrar_gui) 
btn_finalizar_registro.pack(pady=10)

# Inicia com tela de boas-vindas
frame_inicio.pack()

frame_chat = tk.Frame(root)

chat_area = scrolledtext.ScrolledText(frame_chat, height=15, width=50, state='disabled')
chat_area.pack(padx=10, pady=10)

label_status = tk.Label(frame_chat, text="", fg="gray")
label_status.pack()

frame_input = tk.Frame(frame_chat)
frame_input.pack(pady=10)

entry_mensagem = tk.Entry(frame_input, width=40)
entry_mensagem.pack(side=tk.LEFT)
entry_mensagem.bind("<KeyPress>", ao_digitar)

btn_enviar = tk.Button(frame_input, text="Enviar", command=enviar_mensagens)
btn_enviar.pack(side=tk.LEFT, padx=5)

root.mainloop()
