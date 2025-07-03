import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext
from datetime import datetime
import socket
import json
import threading
from time import strftime

timer_digitacao = None
sock = None
usuario = ""
destinatario_atual = ""

def registrar_gui():
    username = entry_novo_usuario.get()
    senha = entry_nova_senha.get()

    if not username or not senha:
        messagebox.showwarning("Campos vazios", "Preencha todos os campos.")
        return

    try:
        cliente_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente_socket.connect(('127.0.0.1', 12345))

        mensagem = {
            "acao": "registrar",
            "username": username,
            "senha": senha
        }

        cliente_socket.send(json.dumps(mensagem).encode('utf-8'))

        resposta = cliente_socket.recv(1024).decode('utf-8')
        resposta_json = json.loads(resposta)

        if resposta_json.get("status") == "ok":
            messagebox.showinfo("Sucesso", "✅ Registro realizado com sucesso.")
            frame_registro.pack_forget()
            frame_login.pack()
        else:
            messagebox.showerror("Erro", f"❌ Erro ao registrar: {resposta_json.get('mensagem')}")

        cliente_socket.close()

    except Exception as e:
        messagebox.showerror("Erro", f"Falha na conexão com o servidor.\n{e}")

def conectar_servidor():
    global sock
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('127.0.0.1', 12345))

def enviar_json(dado):
    mensagem = json.dumps(dado) + '\n'
    sock.send(mensagem.encode('utf-8'))

buffer = ""

def receber_mensagens():
    global sock, buffer
    while True:
        print("[CLIENTE] Esperando mensagens...")
        try:
            dados = sock.recv(4096).decode('utf-8')
            if not dados:
                break

            buffer += dados

            while '\n' in buffer:
                linha, buffer = buffer.split('\n', 1)
                if linha.strip() == "":
                    continue
                try:
                    mensagem = json.loads(linha)
                    print(f"[DEBUG] Linha recebida para JSON: {repr(linha)}")
                    print(f"[CLIENTE] Mensagem recebida: {mensagem}")
                    acao = mensagem.get("acao")
                    print(f"[DEBUG] Linha recebida para JSON: {repr(linha)}")
                    print(f"[CLIENTE] Mensagem recebida: {mensagem}")
                    if acao == "enviar_mensagem":
                        mostrar_mensagem(f"{mensagem['remetente']} ({mensagem['timestamp']}): {mensagem['mensagem']}")
                    elif acao == "status_digitacao":
                        status = f"{mensagem['usuario']} está digitando..." if mensagem['digitando'] else ""
                    # Atualize a label ou status da interface, exemplo:
                        label_status.config(text=status)
                    else:
                        print(f"[WARN] Ação desconhecida: {acao}")
                except json.JSONDecodeError as e:
                    print(f"[ERRO] Falha ao decodificar JSON: {e} - Conteúdo: {repr(linha)}")

        except Exception as e:
            print(f"Erro ao receber mensagens: {e}")
            break
                
def mostrar_mensagem(texto):
    chat_area.config(state='normal')
    chat_area.insert(tk.END, texto + "\n")
    chat_area.config(state='disabled')
    chat_area.see(tk.END)

def ao_digitar(event):
    global timer_digitacao
    enviar_json({
        "acao": "digitando",
        "remetente": usuario,
        "destinatario": destinatario_atual
    })

    if timer_digitacao:
        timer_digitacao.cancel()

    timer_digitacao = threading.Timer(2.0, notificar_parou_digitar)
    timer_digitacao.start()

def registrar_cliente():
    print("Conectando ao servidor...")
    usuario = entry_usuario.get()
    senha = entry_senha.get()

    try:
        cliente_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente_socket.connect(('127.0.0.1', 12345))
        print("Conectado ao servidor.")
    except ConnectionRefusedError:
        return {"status": "erro", "mensagem": "Conexão encerrada."}

    mensagem = {
        "acao": "registrar",
        "username": usuario,
        "senha": senha
    }

    cliente_socket.send(json.dumps(mensagem).encode('utf-8'))
    

    resposta = cliente_socket.recv(1024).decode('utf-8')
    cliente_socket.close()

    return json.loads(resposta)
  

def listar_contatos():
    try:

        cliente_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente_socket.connect(('127.0.0.1', 12345))

        mensagem = {
            "acao": "listar_contatos"
        }
        cliente_socket.send(json.dumps(mensagem).encode('utf-8'))

        resposta = cliente_socket.recv(4096).decode('utf-8')
        cliente_socket.close()
        return json.loads(resposta)
    except:
        return {"status": "erro", "mensagem": "Erro na conexão ao listar contatos."}


def enviar_mensagens():
    global timer_digitacao

    texto = entry_mensagem.get()
    if not texto.strip():
        return
    
    pacote = {
        "acao": "enviar_mensagem",
        "remetente": usuario,
        "destinatario": destinatario_atual,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mensagem": texto
    }
    enviar_json(pacote)
    entry_mensagem.delete(0, tk.END)
    if timer_digitacao:
        timer_digitacao.cancel()
        notificar_parou_digitar()

root = tk.Tk()
root.title("Chat App")
root.geometry("300x250")

# ======= Tela Inicial =======
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

def iniciar_chat():
    global usuario, destinatario_atual, sock

    usuario = entry_usuario.get()
    senha = entry_senha.get()
    destinatario_atual = entry_destinatario.get()

    if not usuario or not senha or not destinatario_atual:
        messagebox.showwarning("Campos vazios", "Preencha usuário, senha e destinatario.")
        return
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', 12345))

        login_msg = {
            "acao": "login",
            "username": usuario,
            "senha": senha
        }
        sock.send(json.dumps(login_msg).encode('utf-8'))
        resposta = json.loads(sock.recv(1024).decode('utf-8'))

        if resposta.get("status") == "ok":
            messagebox.showinfo("Sucesso", "Login realizado com sucesso.")
            frame_login.pack_forget()
            frame_chat.pack()

            threading.Thread(target=receber_mensagens, daemon=True).start()
        else:
            messagebox.showerror("Erro", resposta.get("mensagem"))
            sock.close()
            sock = None
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao conectar ao servidor: {e}")

def conectar_ao_servidor():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('127.0.0.1', 12345))
    return sock

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

    timer_digitacao = threading.Timer(2.0, notificar_parou_digitar)
    timer_digitacao.start()

def notificar_parou_digitar():
    enviar_json = ({
        "acao": "parou_digitacao",
        "remetente": usuario,
        "destinatario": destinatario_atual
    })
    sock.send(json.dumps(enviar_json).encode('utf-8'))

# ======= Tela de Login =======
frame_login = tk.Frame(root)

tk.Label(frame_login, text="Usuário:").pack()
entry_usuario = tk.Entry(frame_login)
entry_usuario.pack()

tk.Label(frame_login, text="Senha:").pack()
entry_senha = tk.Entry(frame_login, show="*")
entry_senha.pack()

tk.Label(frame_login, text="Destinatário:").pack()
entry_destinatario = tk.Entry(frame_login)
entry_destinatario.pack()

btn_entrar_chat = tk.Button(frame_login, text="Entrar no chat", command=iniciar_chat)  # adicione comando depois
btn_entrar_chat.pack(pady=10)

#Tela de Registro 
frame_registro = tk.Frame(root)

tk.Label(frame_registro, text="Novo usuário:").pack()
entry_novo_usuario = tk.Entry(frame_registro)
entry_novo_usuario.pack()

tk.Label(frame_registro, text="Nova senha:").pack()
entry_nova_senha = tk.Entry(frame_registro, show="*")
entry_nova_senha.pack()

btn_finalizar_registro = tk.Button(frame_registro, text="Registrar", command=registrar_gui)  # adicione comando depois
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
