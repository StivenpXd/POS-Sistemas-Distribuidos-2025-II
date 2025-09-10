import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import socket
import threading
import json
import sys
import time
import os
import base64
import hashlib
from pathlib import Path

class MessengerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("P.O.S. CHAT")
        self.root.geometry("700x600")
        
        # Variables de estado
        self.is_server = False
        self.connected = False
        self.private_chats = {}
        self.username = ""
        self.host = ""
        self.port = 12345
        self.clients = {}
        self.connected_users = []
        self.pending_files = {}  # Almacena información de archivos pendientes de descarga
        
        # Crear carpeta para archivos descargados
        self.download_folder = Path("downloads")
        self.download_folder.mkdir(exist_ok=True)
        
        # Crear interfaz de registro
        self.create_registration_interface()
        
    def create_registration_interface(self):
        # Frame principal
        self.registration_frame = ttk.Frame(self.root, padding="20")
        self.registration_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Título
        ttk.Label(self.registration_frame, text="P.O.S. Chat", font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=10)
        
        # Campo de nombre de usuario
        ttk.Label(self.registration_frame, text="Nombre de usuario:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.username_entry = ttk.Entry(self.registration_frame, width=30)
        self.username_entry.grid(row=1, column=1, pady=5, padx=5)
        
        # Selección de modo
        self.mode_var = tk.StringVar(value="client")
        ttk.Radiobutton(self.registration_frame, text="Conectar como usuario", variable=self.mode_var, 
                       value="client", command=self.toggle_mode).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Radiobutton(self.registration_frame, text="Registrar como servidor", variable=self.mode_var, 
                       value="server", command=self.toggle_mode).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Campo de dirección IP (solo para cliente)
        self.ip_label = ttk.Label(self.registration_frame, text="Dirección del servidor:")
        self.ip_label.grid(row=4, column=0, sticky=tk.W, pady=5)
        
        self.ip_entry = ttk.Entry(self.registration_frame, width=30)
        self.ip_entry.grid(row=4, column=1, pady=5, padx=5)
        self.ip_entry.insert(0, "127.0.0.1")
        
        # Botón de conexión
        self.connect_button = ttk.Button(self.registration_frame, text="Conectar", command=self.connect)
        self.connect_button.grid(row=5, column=0, columnspan=2, pady=20)
        
        # Configurar grid
        self.registration_frame.columnconfigure(1, weight=1)
        for i in range(6):
            self.registration_frame.rowconfigure(i, weight=1)
            
        # Inicialmente ocultar campos de IP
        self.toggle_mode()
        
    def toggle_mode(self):
        if self.mode_var.get() == "server":
            self.ip_label.grid_remove()
            self.ip_entry.grid_remove()
            self.connect_button.config(text="Iniciar servidor")
        else:
            self.ip_label.grid()
            self.ip_entry.grid()
            self.connect_button.config(text="Conectar")
            
    def connect(self):
        self.username = self.username_entry.get().strip()
        if not self.username:
            messagebox.showerror("Error", "Por favor ingresa un nombre de usuario")
            return
            
        if self.mode_var.get() == "server":
            self.start_server()
        else:
            self.host = self.ip_entry.get().strip()
            if not self.host:
                messagebox.showerror("Error", "Por favor ingresa la dirección del servidor")
                return
            self.connect_to_server()
            
    def start_server(self):
        self.is_server = True
        try:
            # Crear socket del servidor
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('', self.port))
            self.server_socket.listen(5)
            
            # Iniciar hilo para aceptar conexiones
            self.accept_thread = threading.Thread(target=self.accept_connections, daemon=True)
            self.accept_thread.start()
            
            # El servidor no necesita conectarse a sí mismo como cliente
            # Simplemente crea la interfaz de chat
            self.connected = True
            self.create_chat_interface()
            
            # Mostrar mensaje de que el servidor está funcionando
            self.public_chat_list.insert(tk.END, "Servidor iniciado. Esperando conexiones...")
            self.public_chat_list.yview(tk.END)
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo iniciar el servidor: {str(e)}")
            
    def accept_connections(self):
        self.clients = {}
        while True:
            try:
                client_socket, client_address = self.server_socket.accept()
                # Recibir información de conexión del cliente
                data = client_socket.recv(1024).decode()
                if data:
                    client_info = json.loads(data)
                    username = client_info['username']
                    
                    # Verificar si el nombre de usuario ya está en uso
                    if username in self.clients:
                        error_msg = {
                            'type': 'error',
                            'message': "Nombre de usuario ya en uso"
                        }
                        client_socket.send(json.dumps(error_msg).encode())
                        client_socket.close()
                        continue
                    
                    # Guardar cliente
                    self.clients[username] = client_socket
                    
                    # Actualizar lista de usuarios
                    self.connected_users = list(self.clients.keys())
                    if self.is_server:
                        self.update_user_list()
                    
                    # Notificar a todos los clientes sobre el nuevo usuario
                    self.broadcast_message({
                        'type': 'user_joined',
                        'username': username,
                        'message': f"{username} se ha unido al chat"
                    })
                    
                    # Enviar lista de usuarios conectados al nuevo cliente
                    user_list = list(self.clients.keys())
                    client_socket.send(json.dumps({
                        'type': 'user_list',
                        'users': user_list
                    }).encode())
                    
                    # Iniciar hilo para escuchar mensajes del cliente
                    client_thread = threading.Thread(
                        target=self.handle_client, 
                        args=(client_socket, username),
                        daemon=True
                    )
                    client_thread.start()
                    
            except Exception as e:
                print(f"Error aceptando conexión: {str(e)}")
                break
                
    def handle_client(self, client_socket, username):
        while True:
            try:
                data = client_socket.recv(1024).decode()
                if not data:
                    break
                    
                message_data = json.loads(data)
                
                if message_data['type'] == 'public_message':
                    # Mostrar mensaje en el servidor
                    self.public_chat_list.insert(
                        tk.END, f"{message_data['sender']}: {message_data['message']}"
                    )
                    self.public_chat_list.yview(tk.END)
                    
                    # Reenviar mensaje público a todos los clientes
                    self.broadcast_message(message_data)
                    
                elif message_data['type'] == 'private_message':
                    # Enviar mensaje privado solo al destinatario
                    recipient = message_data['recipient']
                    if recipient in self.clients:
                        self.clients[recipient].send(json.dumps(message_data).encode())
                    else:
                        # Notificar al remitente que el usuario no está disponible
                        error_msg = {
                            'type': 'error',
                            'message': f"El usuario {recipient} no está conectado"
                        }
                        client_socket.send(json.dumps(error_msg).encode())
                
                elif message_data['type'] == 'open_private_chat':
                    # Notificar al destinatario que debe abrir un chat privado
                    recipient = message_data['recipient']
                    if recipient in self.clients:
                        open_chat_msg = {
                            'type': 'open_private_chat',
                            'sender': username
                        }
                        self.clients[recipient].send(json.dumps(open_chat_msg).encode())
                
                elif message_data['type'] == 'file_offer':
                    # Manejar oferta de archivo
                    recipient = message_data.get('recipient', None)
                    if recipient:  # Es un archivo privado
                        if recipient in self.clients:
                            self.clients[recipient].send(json.dumps(message_data).encode())
                        else:
                            error_msg = {
                                'type': 'error',
                                'message': f"El usuario {recipient} no está conectado"
                            }
                            client_socket.send(json.dumps(error_msg).encode())
                    else:  # Es un archivo público
                        self.broadcast_message(message_data)
                        # Mostrar en el servidor también
                        self.public_chat_list.insert(
                            tk.END, f"{message_data['sender']} envió un archivo: {message_data['file_name']}"
                        )
                        self.public_chat_list.yview(tk.END)
                
                elif message_data['type'] == 'file_request':
                    # Manejar solicitud de descarga de archivo
                    file_id = message_data['file_id']
                    if file_id in self.pending_files:
                        file_data = self.pending_files[file_id]
                        file_msg = {
                            'type': 'file_data',
                            'file_id': file_id,
                            'file_name': file_data['file_name'],
                            'file_content': file_data['file_content'],
                            'sender': file_data['sender']
                        }
                        client_socket.send(json.dumps(file_msg).encode())
                    else:
                        error_msg = {
                            'type': 'error',
                            'message': "El archivo solicitado ya no está disponible"
                        }
                        client_socket.send(json.dumps(error_msg).encode())
                        
            except Exception as e:
                print(f"Error manejando cliente {username}: {str(e)}")
                break
                
        # Eliminar cliente desconectado
        if username in self.clients:
            del self.clients[username]
            
        # Actualizar lista de usuarios
        self.connected_users = list(self.clients.keys())
        if self.is_server:
            self.update_user_list()
            
        # Notificar a todos que el usuario se fue
        self.broadcast_message({
            'type': 'user_left',
            'username': username,
            'message': f"{username} ha abandonado el chat"
        })
        
    def broadcast_message(self, message_data):
        # Si somos el servidor, también mostramos el mensaje en nuestra interfaz
        # SOLO si es un mensaje de sistema (user_joined, user_left), NO mensajes públicos
        if self.is_server and message_data['type'] in ['user_joined', 'user_left']:
            self.public_chat_list.insert(tk.END, message_data['message'])
            self.public_chat_list.yview(tk.END)
            
        # Enviar mensaje a todos los clientes conectados
        for client_socket in self.clients.values():
            try:
                client_socket.send(json.dumps(message_data).encode())
            except Exception as e:
                print(f"Error enviando mensaje: {str(e)}")
                
    def connect_to_server(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.host, self.port))
            
            # Enviar información de conexión
            connection_info = json.dumps({
                'type': 'connection',
                'username': self.username
            })
            self.client_socket.send(connection_info.encode())
            
            self.connected = True
            self.create_chat_interface()
            
            # Iniciar hilo para recibir mensajes
            self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
            self.receive_thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo conectar al servidor: {str(e)}")
            
    def create_chat_interface(self):
        # Ocultar frame de registro
        self.registration_frame.grid_remove()
        
        # Crear frame principal del chat
        self.chat_frame = ttk.Frame(self.root, padding="10")
        self.chat_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Banner azul para chat público
        public_banner = tk.Frame(self.chat_frame, height=30, bg="blue")
        public_banner.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))
        ttk.Label(public_banner, text="CHAT PÚBLICO", foreground="white", 
                 background="blue", font=("Arial", 12, "bold")).pack(pady=5)
        
        # Área de mensajes públicos
        self.public_chat_frame = ttk.Frame(self.chat_frame)
        self.public_chat_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10, padx=(0, 5))
        
        # Scrollbar para el área de mensajes
        scrollbar = ttk.Scrollbar(self.public_chat_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox para mostrar mensajes
        self.public_chat_list = tk.Listbox(
            self.public_chat_frame, 
            yscrollcommand=scrollbar.set,
            height=20,
            width=50
        )
        self.public_chat_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.public_chat_list.yview)
        
        # Frame para lista de usuarios
        user_list_frame = ttk.Frame(self.chat_frame)
        user_list_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10, padx=(5, 0))
        
        # Título lista de usuarios
        user_list_label = tk.Frame(user_list_frame, height=30, bg="green")
        user_list_label.pack(fill=tk.X)
        ttk.Label(user_list_label, text="USUARIOS CONECTADOS", foreground="white", 
                 background="green", font=("Arial", 10, "bold")).pack(pady=5)
        
        # Lista de usuarios conectados
        self.user_listbox = tk.Listbox(user_list_frame, height=20, width=20)
        self.user_listbox.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # Vincular evento de doble clic a la lista de usuarios
        self.user_listbox.bind("<Double-Button-1>", self.on_user_double_click)
        
        # Frame para entrada de mensaje
        input_frame = ttk.Frame(self.chat_frame)
        input_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # Campo de entrada de mensaje
        ttk.Label(input_frame, text="Mensaje:").grid(row=0, column=0, sticky=tk.W)
        self.message_entry = ttk.Entry(input_frame, width=50)
        self.message_entry.grid(row=0, column=1, padx=5)
        self.message_entry.bind("<Return>", self.send_public_message)
        
        # Botón de enviar
        self.send_button = ttk.Button(input_frame, text="Enviar", command=self.send_public_message)
        self.send_button.grid(row=0, column=2)
        
        # Botón de enviar archivo (público)
        self.send_file_button = ttk.Button(input_frame, text="Enviar archivo", command=self.send_public_file)
        self.send_file_button.grid(row=0, column=3, padx=5)
        
        # Configurar grid weights
        self.chat_frame.columnconfigure(0, weight=3)
        self.chat_frame.columnconfigure(1, weight=1)
        self.chat_frame.rowconfigure(1, weight=1)
        input_frame.columnconfigure(1, weight=1)
        
        # Hacer que la ventana se expanda
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
    def update_user_list(self):
        """Actualiza la lista de usuarios conectados"""
        self.user_listbox.delete(0, tk.END)
        for user in self.connected_users:
            if user != self.username:  # No mostrar nuestro propio nombre
                self.user_listbox.insert(tk.END, user)
                
    def on_user_double_click(self, event):
        """Maneja el evento de doble clic en un usuario de la lista"""
        selection = self.user_listbox.curselection()
        if selection:
            recipient = self.user_listbox.get(selection[0])
            self.open_private_chat(recipient)
            
    def open_private_chat(self, recipient):
        """Abre una ventana de chat privado con el usuario seleccionado"""
        if recipient == self.username:
            return  # No se puede chatear consigo mismo
            
        # Si el chat privado no existe, crear uno
        if recipient not in self.private_chats:
            if self.is_server:
                # Si somos servidor, crear directamente la ventana
                self.create_private_chat_window(recipient)
            else:
                # Si somos cliente, notificar al servidor
                open_chat_msg = {
                    'type': 'open_private_chat',
                    'recipient': recipient
                }
                try:
                    self.client_socket.send(json.dumps(open_chat_msg).encode())
                    self.create_private_chat_window(recipient)
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo abrir el chat privado: {str(e)}")
        else:
            # Si ya existe, traer la ventana al frente
            self.private_chats[recipient]['window'].lift()
            
    def send_public_message(self, event=None):
        """Envía un mensaje público"""
        message = self.message_entry.get().strip()
        if not message:
            return
            
        self.message_entry.delete(0, tk.END)
        
        # Mensaje público
        if self.is_server:
            # Si somos servidor, mostrar directamente el mensaje
            self.public_chat_list.insert(tk.END, f"{self.username}: {message}")
            self.public_chat_list.yview(tk.END)
            
            # Y enviarlo a todos los clientes
            message_data = {
                'type': 'public_message',
                'sender': self.username,
                'message': message
            }
            self.broadcast_message(message_data)
        else:
            # Si somos cliente, enviar al servidor
            message_data = {
                'type': 'public_message',
                'sender': self.username,
                'message': message
            }
            
            try:
                self.client_socket.send(json.dumps(message_data).encode())
                # Mostrar el mensaje localmente mientras esperamos la respuesta del servidor
                self.public_chat_list.insert(tk.END, f"{self.username}: {message}")
                self.public_chat_list.yview(tk.END)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo enviar el mensaje: {str(e)}")
                
    def send_private_message(self, recipient, message):
        """Envía un mensaje privado"""
        if self.is_server:
            # Si somos servidor, manejamos directamente
            if recipient in self.clients:
                message_data = {
                    'type': 'private_message',
                    'sender': self.username,
                    'recipient': recipient,
                    'message': message
                }
                self.clients[recipient].send(json.dumps(message_data).encode())
            
            # Mostrar el mensaje en nuestra ventana
            if recipient in self.private_chats:
                self.private_chats[recipient]['chat_list'].insert(
                    tk.END, f"Tú: {message}"
                )
                self.private_chats[recipient]['chat_list'].yview(tk.END)
        else:
            # Si somos cliente, enviamos al servidor
            message_data = {
                'type': 'private_message',
                'sender': self.username,
                'recipient': recipient,
                'message': message
            }
            
            try:
                self.client_socket.send(json.dumps(message_data).encode())
                if recipient in self.private_chats:
                    self.private_chats[recipient]['chat_list'].insert(
                        tk.END, f"Tú: {message}"
                    )
                    self.private_chats[recipient]['chat_list'].yview(tk.END)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo enviar el mensaje: {str(e)}")
    
    def send_public_file(self):
        """Abre un diálogo para seleccionar y enviar un archivo al chat público"""
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo para enviar",
            filetypes=[("Todos los archivos", "*.*")]
        )
        
        if file_path:
            self.send_file(file_path, None)  # None indica que es público
    
    def send_private_file(self, recipient):
        """Abre un diálogo para seleccionar y enviar un archivo al chat privado"""
        file_path = filedialog.askopenfilename(
            title=f"Seleccionar archivo para enviar a {recipient}",
            filetypes=[("Todos los archivos", "*.*")]
        )
        
        if file_path:
            self.send_file(file_path, recipient)
    
    def send_file(self, file_path, recipient):
        """Envía un archivo al servidor o cliente"""
        try:
            # Leer el archivo en modo binario
            with open(file_path, 'rb') as file:
                file_content = file.read()
            
            # Codificar el contenido en base64 para transmitirlo
            encoded_content = base64.b64encode(file_content).decode('utf-8')
            file_name = os.path.basename(file_path)
            
            # Generar un ID único para el archivo
            file_id = hashlib.md5(f"{file_name}{time.time()}".encode()).hexdigest()
            
            # Crear mensaje de oferta de archivo
            file_msg = {
                'type': 'file_offer',
                'file_id': file_id,
                'file_name': file_name,
                'file_size': len(file_content),
                'sender': self.username
            }
            
            # Añadir destinatario si es un archivo privado
            if recipient:
                file_msg['recipient'] = recipient
            
            # Si somos el servidor, manejamos directamente
            if self.is_server:
                if recipient:  # Archivo privado
                    if recipient in self.clients:
                        # Guardar archivo temporalmente
                        self.pending_files[file_id] = {
                            'file_name': file_name,
                            'file_content': encoded_content,
                            'sender': self.username
                        }
                        # Enviar oferta al destinatario
                        self.clients[recipient].send(json.dumps(file_msg).encode())
                        # Mostrar en nuestro chat privado
                        if recipient in self.private_chats:
                            self.private_chats[recipient]['chat_list'].insert(
                                tk.END, f"Tú enviaste un archivo: {file_name}"
                            )
                            self.private_chats[recipient]['chat_list'].yview(tk.END)
                    else:
                        messagebox.showerror("Error", f"El usuario {recipient} no está conectado")
                else:  # Archivo público
                    # Guardar archivo temporalmente
                    self.pending_files[file_id] = {
                        'file_name': file_name,
                        'file_content': encoded_content,
                        'sender': self.username
                    }
                    # Enviar a todos los clientes
                    self.broadcast_message(file_msg)
                    # Mostrar en el servidor también
                    self.public_chat_list.insert(
                        tk.END, f"{self.username} envió un archivo: {file_name}"
                    )
                    self.public_chat_list.yview(tk.END)
            else:
                # Enviar al servidor
                self.client_socket.send(json.dumps(file_msg).encode())
                
                # Guardar archivo localmente para poder enviarlo cuando se solicite
                self.pending_files[file_id] = {
                    'file_name': file_name,
                    'file_content': encoded_content,
                    'sender': self.username
                }
                
                # Mostrar mensaje localmente
                if recipient:
                    if recipient in self.private_chats:
                        self.private_chats[recipient]['chat_list'].insert(
                            tk.END, f"Tú enviaste un archivo: {file_name}"
                        )
                        self.private_chats[recipient]['chat_list'].yview(tk.END)
                else:
                    self.public_chat_list.insert(
                        tk.END, f"Tú enviaste un archivo: {file_name}"
                    )
                    self.public_chat_list.yview(tk.END)
                    
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo enviar el archivo: {str(e)}")
    
    def request_file_download(self, file_id, file_name, sender):
        """Solicita la descarga de un archivo"""
        try:
            if self.is_server:
                # Si somos servidor, buscar el archivo en nuestros archivos pendientes
                if file_id in self.pending_files:
                    file_data = self.pending_files[file_id]
                    self.save_file(file_data['file_content'], file_data['file_name'], file_data['sender'])
                else:
                    messagebox.showerror("Error", "El archivo ya no está disponible")
            else:
                # Si somos cliente, solicitar el archivo al servidor
                request_msg = {
                    'type': 'file_request',
                    'file_id': file_id
                }
                self.client_socket.send(json.dumps(request_msg).encode())
                
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo descargar el archivo: {str(e)}")
    
    def save_file(self, encoded_content, file_name, sender):
        """Guarda un archivo recibido en la carpeta de descargas"""
        try:
            # Decodificar el contenido base64
            file_content = base64.b64decode(encoded_content)
            
            # Crear un nombre único para evitar sobrescribir archivos
            base_name, extension = os.path.splitext(file_name)
            counter = 1
            unique_name = file_name
            
            while os.path.exists(self.download_folder / unique_name):
                unique_name = f"{base_name}_{counter}{extension}"
                counter += 1
            
            # Guardar el archivo
            file_path = self.download_folder / unique_name
            with open(file_path, 'wb') as file:
                file.write(file_content)
            
            # Mostrar mensaje de éxito
            messagebox.showinfo("Descarga completada", 
                               f"Archivo '{file_name}' de {sender} guardado como '{unique_name}'")
            
            # Abrir el archivo si el usuario lo desea
            if messagebox.askyesno("Abrir archivo", "¿Desea abrir el archivo descargado?"):
                os.startfile(file_path)  # Funciona en Windows
                # Para otros sistemas operativos, necesitarías implementar una solución diferente
                
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el archivo: {str(e)}")
                    
    def create_private_chat_window(self, recipient):
        # Si ya existe una ventana para este chat, solo traerla al frente
        if recipient in self.private_chats:
            self.private_chats[recipient]['window'].lift()
            return
            
        # Crear nueva ventana para chat privado
        private_window = tk.Toplevel(self.root)
        private_window.title(f"Chat privado con {recipient}")
        private_window.geometry("500x400")
        
        # Banner rojo para chat privado
        private_banner = tk.Frame(private_window, height=30, bg="red")
        private_banner.pack(fill=tk.X)
        ttk.Label(private_banner, text=f"CHAT PRIVADO CON {recipient}", 
                 foreground="white", background="red", font=("Arial", 10, "bold")).pack(pady=5)
        
        # Frame principal
        main_frame = ttk.Frame(private_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Frame para mensajes
        chat_frame = ttk.Frame(main_frame)
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(chat_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox para mensajes
        chat_list = tk.Listbox(chat_frame, yscrollcommand=scrollbar.set, height=15)
        chat_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=chat_list.yview)
        
        # Frame para entrada
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X)
        
        # Campo de entrada
        private_entry = ttk.Entry(input_frame)
        private_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Botón de enviar
        send_button = ttk.Button(input_frame, text="Enviar", width=10)
        send_button.pack(side=tk.RIGHT)
        
        # Botón de enviar archivo
        send_file_button = ttk.Button(input_frame, text="Enviar archivo", 
                                     command=lambda: self.send_private_file(recipient))
        send_file_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Función para enviar mensaje privado
        def send_private():
            message = private_entry.get().strip()
            if message:
                self.send_private_message(recipient, message)
                private_entry.delete(0, tk.END)
        
        # Vincular eventos
        send_button.config(command=send_private)
        private_entry.bind("<Return>", lambda e: send_private())
        
        # Establecer foco en el campo de entrada
        private_entry.focus_set()
        
        # Guardar referencia al chat privado
        self.private_chats[recipient] = {
            'window': private_window,
            'chat_list': chat_list,
            'entry': private_entry
        }
        
        # Configurar cierre de ventana
        def on_closing():
            if recipient in self.private_chats:
                del self.private_chats[recipient]
            private_window.destroy()
            
        private_window.protocol("WM_DELETE_WINDOW", on_closing)
        
    def receive_messages(self):
        while self.connected:
            try:
                data = self.client_socket.recv(1024).decode()
                if not data:
                    break
                    
                message_data = json.loads(data)
                
                if message_data['type'] == 'public_message':
                    # Mostrar mensaje público
                    self.public_chat_list.insert(
                        tk.END, f"{message_data['sender']}: {message_data['message']}"
                    )
                    self.public_chat_list.yview(tk.END)
                    
                elif message_data['type'] == 'private_message':
                    # Mostrar mensaje privado
                    sender = message_data['sender']
                    if sender not in self.private_chats:
                        self.create_private_chat_window(sender)
                    
                    self.private_chats[sender]['chat_list'].insert(
                        tk.END, f"{sender}: {message_data['message']}"
                    )
                    self.private_chats[sender]['chat_list'].yview(tk.END)
                    
                elif message_data['type'] == 'open_private_chat':
                    # Alguien quiere iniciar un chat privado con nosotros
                    sender = message_data['sender']
                    if sender not in self.private_chats:
                        self.create_private_chat_window(sender)
                    
                elif message_data['type'] in ['user_joined', 'user_left']:
                    # Mostrar notificación de usuario
                    self.public_chat_list.insert(tk.END, message_data['message'])
                    self.public_chat_list.yview(tk.END)
                    
                elif message_data['type'] == 'user_list':
                    # Actualizar lista de usuarios conectados
                    self.connected_users = message_data['users']
                    self.update_user_list()
                    
                elif message_data['type'] == 'error':
                    # Mostrar mensaje de error
                    messagebox.showerror("Error", message_data['message'])
                
                elif message_data['type'] == 'file_offer':
                    # Mostrar oferta de archivo
                    file_id = message_data['file_id']
                    file_name = message_data['file_name']
                    file_size = message_data['file_size']
                    sender = message_data['sender']
                    
                    # Determinar si es público o privado
                    is_private = 'recipient' in message_data
                    
                    if is_private:
                        # Mostrar en chat privado
                        if sender in self.private_chats:
                            self.private_chats[sender]['chat_list'].insert(
                                tk.END, f"{sender} envió un archivo: {file_name} ({file_size} bytes)"
                            )
                            # Añadir botón de descarga
                            self.private_chats[sender]['chat_list'].insert(
                                tk.END, f"   [Descargar archivo]"
                            )
                            # Guardar información del archivo para descarga
                            last_index = self.private_chats[sender]['chat_list'].size() - 1
                            self.private_chats[sender]['chat_list'].itemconfig(
                                last_index, fg="blue", selectbackground="lightblue"
                            )
                            # Vincular evento de clic para descargar
                            self.private_chats[sender]['chat_list'].bind(
                                "<Button-1>", 
                                lambda e, fid=file_id, fn=file_name, s=sender: 
                                self.on_file_click(e, fid, fn, s)
                            )
                        else:
                            # Si no tenemos abierto el chat, abrirlo primero
                            self.create_private_chat_window(sender)
                            # Luego mostrar el archivo
                            self.private_chats[sender]['chat_list'].insert(
                                tk.END, f"{sender} envió un archivo: {file_name} ({file_size} bytes)"
                            )
                            self.private_chats[sender]['chat_list'].insert(
                                tk.END, f"   [Descargar archivo]"
                            )
                            last_index = self.private_chats[sender]['chat_list'].size() - 1
                            self.private_chats[sender]['chat_list'].itemconfig(
                                last_index, fg="blue", selectbackground="lightblue"
                            )
                            self.private_chats[sender]['chat_list'].bind(
                                "<Button-1>", 
                                lambda e, fid=file_id, fn=file_name, s=sender: 
                                self.on_file_click(e, fid, fn, s)
                            )
                    else:
                        # Mostrar en chat público
                        self.public_chat_list.insert(
                            tk.END, f"{sender} envió un archivo: {file_name} ({file_size} bytes)"
                        )
                        # Añadir botón de descarga
                        self.public_chat_list.insert(
                            tk.END, f"   [Descargar archivo]"
                        )
                        # Guardar información del archivo para descarga
                        last_index = self.public_chat_list.size() - 1
                        self.public_chat_list.itemconfig(
                            last_index, fg="blue", selectbackground="lightblue"
                        )
                        # Vincular evento de clic para descargar
                        self.public_chat_list.bind(
                            "<Button-1>", 
                            lambda e, fid=file_id, fn=file_name, s=sender: 
                            self.on_file_click(e, fid, fn, s)
                        )
                
                elif message_data['type'] == 'file_data':
                    # Recibir datos de archivo solicitado
                    file_id = message_data['file_id']
                    file_name = message_data['file_name']
                    file_content = message_data['file_content']
                    sender = message_data['sender']
                    
                    # Guardar el archivo
                    self.save_file(file_content, file_name, sender)
                    
            except Exception as e:
                print(f"Error recibiendo mensajes: {str(e)}")
                if not self.is_server:  # Solo mostrar error si no somos servidor
                    break
                
        # Si llegamos aquí, la conexión se perdió (solo para clientes)
        if not self.is_server and self.connected:
            self.connected = False
            messagebox.showerror("Error", "Se perdió la conexión con el servidor")
            self.root.destroy()
    
    def on_file_click(self, event, file_id, file_name, sender):
        """Maneja el clic en un enlace de descarga de archivo"""
        # Determinar en qué Listbox se hizo clic
        widget = event.widget
        index = widget.nearest(event.y)
        
        # Verificar si el clic fue en el elemento de descarga
        if index >= 0:
            item_text = widget.get(index)
            if "[Descargar archivo]" in item_text:
                self.request_file_download(file_id, file_name, sender)

def main():
    root = tk.Tk()
    app = MessengerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()