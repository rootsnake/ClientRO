# Ficheiro: connect-char.ps1

$server = "127.0.0.1"
$loginPort = 6900
$packetVersion = 20211105
$username = "testuser"
$password = "testpassword"

Write-Host "[Bypass] A ligar ao Login-Server (${server}:${loginPort})..." -ForegroundColor Cyan

try {
    # 1. Conectar ao Login-Server
    $client = New-Object System.Net.Sockets.TcpClient($server, $loginPort)
    $stream = $client.GetStream()

    # Construir pacote 0x0064 (55 bytes)
    $packet = New-Object byte[] 55
    $packet[0] = 0x64
    $packet[1] = 0x00
    [BitConverter]::GetBytes($packetVersion).CopyTo($packet, 2)
    [System.Text.Encoding]::ASCII.GetBytes($username).CopyTo($packet, 6)
    [System.Text.Encoding]::ASCII.GetBytes($password).CopyTo($packet, 30)

    Write-Host "[Bypass] A enviar dados de autenticação para o Login..." -ForegroundColor Yellow
    $stream.Write($packet, 0, $packet.Length)
    $stream.Flush()

    # 2. Ler a resposta de 224 bytes do Login-Server
    $buffer = New-Object byte[] 224
    $bytesRead = $stream.Read($buffer, 0, $buffer.Length)
    $client.Close()

    if ($bytesRead -eq 224) {
        Write-Host "[SUCESSO] Resposta de 224 bytes capturada do Login-Server!" -ForegroundColor Green

        # Extração dos dados de sessão dos 224 bytes (Offsets padrão rAthena)
        # Offset 2: Session ID 1 (Auth Code 1)
        $sessionId1 = [BitConverter]::ToUInt32($buffer, 2)
        # Offset 6: Account ID (AID)
        $accountId = [BitConverter]::ToUInt32($buffer, 6)
        # Offset 10: Session ID 2 (Auth Code 2)
        $sessionId2 = [BitConverter]::ToUInt32($buffer, 10)
        # Offset 26: Sex (0 = Femea, 1 = Macho)
        $sex = $buffer[26]

        Write-Host "[Parse] Dados extraídos -> AID: ${accountId} | Sessão 1: ${sessionId1} | Sessão 2: ${sessionId2} | Sex: ${sex}" -ForegroundColor Cyan

        $charIp = "127.0.0.1"
        $charPort = 6121

        # 3. Conectar ao Char-Server (Porta 6121)
        Write-Host "[Bypass] A ligar ao Char-Server em ${charIp}:${charPort}..." -ForegroundColor Cyan
        $charClient = New-Object System.Net.Sockets.TcpClient($charIp, $charPort)
        $charStream = $charClient.GetStream()

        if ($charClient.Connected) {
            Write-Host "[SUCESSO] Conectado ao Char-Server! A enviar pacote de autenticação (0x0065)..." -ForegroundColor Green

            # Construir pacote 0x0065 (Autenticação no Char-Server)
            # Estrutura típica: [Opcode 2 bytes][AID 4 bytes][SessionID1 4 bytes][SessionID2 4 bytes][Tick 4 bytes][Sex 1 byte] -> Total 19 bytes
            $charPacket = New-Object byte[] 19
            # Opcode 0x0065
            $charPacket[0] = 0x65
            $charPacket[1] = 0x00
            # Account ID
            [BitConverter]::GetBytes($accountId).CopyTo($charPacket, 2)
            # Session ID 1
            [BitConverter]::GetBytes($sessionId1).CopyTo($charPacket, 6)
            # Session ID 2
            [BitConverter]::GetBytes($sessionId2).CopyTo($charPacket, 10)
            # Tick (0 por defeito)
            [BitConverter]::GetBytes(0).CopyTo($charPacket, 14)
            # Sex
            $charPacket[18] = $sex

            # Enviar para o Char-Server
            $charStream.Write($charPacket, 0, $charPacket.Length)
            $charStream.Flush()
            Write-Host "[Bypass] Pacote 0x0065 enviado com sucesso ao Char-Server!" -ForegroundColor Green

            # 4. Ler a resposta do Char-Server (Lista de Personagens)
            $charBuffer = New-Object byte[] 1024
            $charBytesRead = $charStream.Read($charBuffer, 0, $charBuffer.Length)
            
            if ($charBytesRead -gt 0) {
                Write-Host "[SUCESSO ABSOLUTO] Char-Server respondeu com ${charBytesRead} bytes!" -ForegroundColor Green
                Write-Host $charBuffer[0..($charBytesRead-1)] -ForegroundColor DarkGray
            }
        }
        
        $charClient.Close()
    } else {
        Write-Host "[ERRO] O servidor respondeu com um tamanho inesperado: $bytesRead bytes." -ForegroundColor Red
    }

} catch {
    Write-Host "[ERRO DE REDE] $($_.Exception.Message)" -ForegroundColor Red
}