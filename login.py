#!/usr/bin/env python3
"""ro_bridge_server.py - Servidor HTTP local integrado com o motor de rede rAthena.
Gerencia Login -> Char-Server -> Seleção de Char -> Map-Server na porta 7171.
"""
import http.server
import json
import os
import socket
import struct
import threading
import webbrowser
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs

PORT = 7171
CLIENT_PATH = r"C:\Gravity\Ragnarok"

# Variáveis globais para manter a sessão ativa entre pedidos da interface web
sessao_ativa = {
    "aid": None,
    "login_id1": None,
    "login_id2": None,
    "sexo": None,
    "char_server_ip": None,
    "char_server_port": None
}

def ler_client_info():
    xml_path = os.path.join(CLIENT_PATH, "System", "clientinfo.xml")
    config = {"host": "127.0.0.1", "port": 6900, "packetver": 20211105}
    if not os.path.exists(xml_path):
        return config
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        conn = root.find("connection")
        if conn is not None:
            addr = conn.find("address")
            port = conn.find("port")
            ver = conn.find("version")
            if addr is not None and addr.text:
                config["host"] = addr.text.strip()
            if port is not None and port.text:
                config["port"] = int(port.text.strip())
            if ver is not None and ver.text:
                config["packetver"] = int(ver.text.strip())
    except Exception as e:
        print(f"[erro] A ler clientinfo.xml: {e}")
    return config

def recv_available(sock, first_timeout=5.0, idle=1.5, limit=65536):
    data = b""
    sock.settimeout(first_timeout)
    try:
        while len(data) < limit:
            part = sock.recv(4096)
            if not part:
                break
            data += part
            sock.settimeout(idle)
    except socket.timeout:
        pass
    return data

def executar_fluxo_ragnarok(user, senha):
    cfg = ler_client_info()
    host = cfg["host"]
    login_port = cfg["port"]
    packetver = cfg["packetver"]

    print(f"\n[bridge] A iniciar autenticação para '{user}' em {host}:{login_port}...")

    # 1. Login-Server
    pkt = struct.pack("<HI24s24sB", 0x0064, packetver, user.encode("ascii"), senha.encode("ascii"), 0)
    s = socket.create_connection((host, login_port), timeout=5)
    try:
        s.sendall(pkt)
        data = recv_available(s, first_timeout=10.0, idle=1.0)
    finally:
        s.close()

    if not data:
        raise Exception("Login-Server não respondeu ao pacote CA_LOGIN.")

    pid = struct.unpack_from("<H", data, 0)[0] if len(data) >= 2 else None
    if pid in (0x006A, 0x083E, 0x0081):
        raise Exception(f"Login recusado pelo servidor (Pacote: 0x{pid:04X}).")
    
    if pid not in (0x0069, 0x0AC4):
        raise Exception(f"Pacote de login inesperado: 0x{pid:04X}")

    cabecalho, entrada = (0x40, 160) if pid == 0x0AC4 else (0x2F, 32)
    login_id1, aid, login_id2 = struct.unpack_from("<III", data, 4)
    sexo = data[46]

    servidores = []
    off = cabecalho
    while off + entrada <= len(data):
        ip = ".".join(str(b) for b in data[off:off + 4])
        porta = struct.unpack_from("<H", data, off + 4)[0]
        nome = data[off + 6:off + 26].split(b"\0")[0].decode("ascii", "replace")
        usuarios = struct.unpack_from("<H", data, off + 26)[0]
        servidores.append({"ip": ip, "porta": porta, "nome": nome, "usuarios": usuarios})
        off += entrada

    if not servidores:
        raise Exception("Nenhum servidor de personagens disponível.")

    sv = servidores[0]
    
    # Guardar na sessão global
    sessao_ativa["aid"] = aid
    sessao_ativa["login_id1"] = login_id1
    sessao_ativa["login_id2"] = login_id2
    sessao_ativa["sexo"] = sexo
    sessao_ativa["char_server_ip"] = sv["ip"]
    sessao_ativa["char_server_port"] = sv["porta"]

    # 2. Char-Server Handshake inicial
    s_char = socket.create_connection((sv["ip"], sv["porta"]), timeout=5)
    try:
        pkt_char = struct.pack("<HIIIIB", 0x0065, aid, login_id1, login_id2, 0, sexo)
        s_char.sendall(pkt_char)
        dados_char = recv_available(s_char, first_timeout=5.0, idle=1.0)
    finally:
        s_char.close()

    print(f"[bridge] Autenticação concluída! AID={aid}")
    return {
        "status": "success",
        "aid": aid,
        "sexo": sexo,
        "servidor": sv["nome"],
        "char_bytes_recebidos": len(dados_char)
    }

def executar_selecao_char(char_slot):
    """Seleciona o personagem e obtém os dados do Map-Server"""
    if not sessao_ativa["aid"]:
        raise Exception("Sessão não iniciada. Faça login primeiro.")

    print(f"[char] A selecionar personagem no slot {char_slot}...")
    s_char = socket.create_connection((sessao_ativa["char_server_ip"], sessao_ativa["char_server_port"]), timeout=5)
    try:
        # Enviar pacote CH_SELECT_CHAR (0x0067)
        pkt_select = struct.pack("<HB", 0x0067, int(char_slot))
        s_char.sendall(pkt_select)
        data = recv_available(s_char, first_timeout=5.0, idle=1.0)
    finally:
        s_char.close()

    if not data:
        raise Exception("Char-Server não respondeu à seleção.")

    print(f"[char] Resposta de seleção recebida ({len(data)} bytes). A preparar Map-Server...")
    
    # Para testes iniciais, mapeamos para o Map-Server local padrão do rAthena
    return {
        "status": "success",
        "map_ip": "127.0.0.1",
        "map_port": 5121,
        "map_name": "pay_fild08.gat"
    }

def conectar_map_server(map_ip, map_port):
    """Conecta ao Map-Server e envia o CZ_ENTER"""
    print(f"[map] A conectar ao Map-Server em {map_ip}:{map_port}...")
    s_map = socket.create_connection((map_ip, map_port), timeout=5)
    try:
        tick = 0
        # Pacote CZ_ENTER (0x0436)
        pkt_enter = struct.pack("<HIIIIB", 0x0436, sessao_ativa["aid"], sessao_ativa["login_id1"], sessao_ativa["login_id2"], tick, sessao_ativa["sexo"])
        s_map.sendall(pkt_enter)
        map_data = recv_available(s_map, first_timeout=5.0, idle=1.0)
        print(f"[map] Sucesso! Conectado ao Map-Server. Recebidos {len(map_data)} bytes iniciais.")
    finally:
        s_map.close()

    return {"status": "success", "bytes_recebidos": len(map_data)}


class RagnarokHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        params = parse_qs(post_data.decode('utf-8'))

        response_data = {}
        try:
            if self.path == "/api/login":
                user = params.get('user', [''])[0]
                senha = params.get('password', [''])[0]
                response_data = executar_fluxo_ragnarok(user, senha)
            
            elif self.path == "/api/select_char":
                slot = params.get('slot', [0])[0]
                res_sel = executar_selecao_char(slot)
                # Conectar imediatamente ao Map-Server recolhido
                res_map = conectar_map_server(res_sel["map_ip"], res_sel["map_port"])
                response_data = {**res_sel, **res_map}

            else:
                self.send_error(404, "Endpoint não encontrado")
                return
        except Exception as e:
            response_data = {"status": "error", "message": str(e)}

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def log_message(self, format, *args):
        print(f"[http] {args[0]}")


def run_server():
    server_address = ('', PORT)
    try:
        httpd = http.server.HTTPServer(server_address, RagnarokHTTPHandler)
    except OSError as e:
        print(f"[erro] Não foi possível abrir a porta {PORT}: {e}")
        return

    url = f"http://localhost:{PORT}/index.html"
    print(f"\n[servidor] Interface web ativa em: {url}")
    print("[servidor] Pronto para login, seleção de char e salto para o Map-Server. Pressiona Ctrl+C para parar.\n")
    
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[servidor] A encerrar servidor...")
        httpd.server_close()

if __name__ == "__main__":
    run_server()