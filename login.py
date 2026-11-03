#!/usr/bin/env python3
"""ro_probe.py - sonda de protocolo rAthena (login -> char-server), somente diagnostico.

Uso:
    python login.py --user testuser
    (a senha é pedida no terminal; ou use a variavel de ambiente RO_PASS)
"""
import argparse
import getpass
import os
import socket
import struct
import sys

NOMES_CHAR = {
    0x006B: "HC_ACCEPT_ENTER (lista de personagens, formato antigo)",
    0x082D: "HC_ACCEPT_ENTER2 (cabecalho da lista de personagens)",
    0x09A0: "HC_CHARLIST_NOTIFY",
    0x099D: "HC_ACCEPT_ENTER3 (lista de personagens)",
    0x006C: "HC_REFUSE_ENTER (recusado)",
    0x08B9: "HC_SECOND_PASSWD_LOGIN (pede/valida PIN)",
}


def hexdump(data, prefix="  "):
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        hx = " ".join(f"{b:02x}" for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"{prefix}{i:04x}  {hx:<47}  {asc}")


def recv_exact(sock, n, timeout=5.0):
    sock.settimeout(timeout)
    buf = b""
    while len(buf) < n:
        part = sock.recv(n - len(buf))
        if not part:
            raise ConnectionError(f"conexao fechada com {len(buf)}/{n} bytes recebidos")
        buf += part
    return buf


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


def fazer_login(host, port, user, senha, packetver):
    pkt = struct.pack("<HI24s24sB", 0x0064, packetver, user.encode("ascii"), senha.encode("ascii"), 0)
    assert len(pkt) == 55
    print(f"[login] conectando em {host}:{port} (PACKETVER {packetver})")
    try:
        s = socket.create_connection((host, port), timeout=5)
    except socket.timeout:
        print("[login] o TCP nem conectou (timeout). Veja o mapeamento de portas do Docker.")
        return None
    try:
        print("[login] TCP conectado; enviando CA_LOGIN (55 bytes)")
        s.sendall(pkt)
        data = recv_available(s, first_timeout=10.0, idle=1.0)
        if not data:
            print("[login] SEM RESPOSTA em 10s: o servidor aceitou a conexao mas nao respondeu ao pacote.")
            return None
        print(f"[login] recebidos {len(data)} bytes:")
        hexdump(data[:96])
        pid = struct.unpack_from("<H", data, 0)[0] if len(data) >= 2 else None
        if pid == 0x006A and len(data) >= 3:
            print(f"[login] RECUSADO (0x006A), codigo={data[2]} "
                  "(0 conta inexistente, 1 senha incorreta, 3 rejeitado pelo servidor, 5 versao do cliente)")
            return None
        if pid == 0x0081 and len(data) >= 3:
            motivos = {1: "servidor fechado (nao ha char-server registrado no login)",
                       2: "ja existe alguem logado com esta conta", 4: "servidor lotado",
                       8: "o servidor ainda reconhece o ultimo login desta conta"}
            print(f"[login] CONTA ACEITA, mas conexao negada (0x0081), codigo={data[2]}: "
                  f"{motivos.get(data[2], 'ver tabela do rAthena')}")
            return None
        if pid == 0x083E:
            print("[login] RECUSADO (0x083E)")
            return None
        if pid not in (0x0069, 0x0AC4):
            print(f"[login] pacote inesperado (id={pid!r}); o dump acima mostra o que chegou.")
            return None
        plen = struct.unpack_from("<H", data, 2)[0]
        if len(data) < plen:
            data += recv_exact(s, plen - len(data))
    finally:
        s.close()

    print(f"[login] pacote aceito: {len(data)} bytes")
    hexdump(data[:80])
    cabecalho, entrada = (0x40, 160) if pid == 0x0AC4 else (0x2F, 32)
    login_id1, aid, login_id2 = struct.unpack_from("<III", data, 4)
    sexo = data[46]
    print(f"[login] AID={aid} login_id1={login_id1} login_id2={login_id2} sexo={sexo} (0=F, 1=M)")
    servidores = []
    off = cabecalho
    while off + entrada <= len(data):
        ip = ".".join(str(b) for b in data[off:off + 4])
        porta = struct.unpack_from("<H", data, off + 4)[0]
        nome = data[off + 6:off + 26].split(b"\0")[0].decode("ascii", "replace")
        usuarios = struct.unpack_from("<H", data, off + 26)[0]
        servidores.append({"ip": ip, "porta": porta, "nome": nome, "usuarios": usuarios})
        off += entrada
    for sv in servidores:
        print(f"[login] servidor de personagens: {sv['nome']!r} em {sv['ip']}:{sv['porta']} "
              f"({sv['usuarios']} online)  <- e isto que o cliente recebe")
    return {"aid": aid, "id1": login_id1, "id2": login_id2, "sexo": sexo, "servidores": servidores}


def sondar_char(info, sv):
    print(f"\n[char] conectando em {sv['ip']}:{sv['porta']}")
    s = socket.create_connection((sv["ip"], sv["porta"]), timeout=5)
    try:
        pkt = struct.pack("<HIIIIB", 0x0065, info["aid"], info["id1"], info["id2"], 0, info["sexo"])
        assert len(pkt) == 19, f"Tamanho invalido: {len(pkt)} bytes (esperado 19)"
        
        s.sendall(pkt)
        dados = recv_available(s, first_timeout=5.0, idle=1.0)
    finally:
        s.close()
        
    if not dados:
        print("[char] o servidor nao respondeu (timeout ou conexao fechada)")
        return
        
    print(f"[char] recebidos {len(dados)} bytes:")
    hexdump(dados)
    if len(dados) >= 4:
        eco = struct.unpack_from("<I", dados, 0)[0]
        print(f"[char] primeiros 4 bytes = {eco} ({'bate' if eco == info['aid'] else 'NAO bate'} com o AID)")
    if len(dados) >= 6:
        pid = struct.unpack_from("<H", dados, 4)[0]
        print(f"[char] proximo pacote: id=0x{pid:04X} {NOMES_CHAR.get(pid, '(desconhecido, ver o dump)')}")
    print("\n[char] sucesso no handshake com o Char-Server!")


def main():
    ap = argparse.ArgumentParser(description="Sonda de protocolo rAthena (login -> char)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--login-port", type=int, default=6900)
    ap.add_argument("--packetver", type=int, default=20211105)
    ap.add_argument("--user", required=True)
    args = ap.parse_args()

    senha = os.environ.get("RO_PASS") or getpass.getpass("Senha da conta de jogo: ")
    try:
        info = fazer_login(args.host, args.login_port, args.user, senha, args.packetver)
    except (OSError, ConnectionError, socket.timeout) as e:
        sys.exit(f"[erro] {e}")
    if not info or not info["servidores"]:
        sys.exit("[fim] sem sessao ou sem servidor de personagens.")
    try:
        sondar_char(info, info["servidores"][0])
    except (OSError, ConnectionError, socket.timeout) as e:
        sys.exit(f"[erro] {e}")


if __name__ == "__main__":
    main()