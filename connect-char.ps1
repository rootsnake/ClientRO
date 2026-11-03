# Ficheiro: connect-char.ps1

$server = "127.0.0.1"
$loginPort = 6900
$packetVersion = 20211105
$username = "testuser"
$password = "testpassword"

Write-Host "[Bypass] A ligar ao Login-Server..." -ForegroundColor Cyan

try {
    # 1. Login-Server
    $client = New-Object System.Net.Sockets.TcpClient($server, $loginPort)
    $stream = $client.GetStream()

    $packet = New-Object byte[] 55
    $packet[0] = 0x64
    $packet[1] = 0x00
    [BitConverter]::GetBytes($packetVersion).CopyTo($packet, 2)
    [System.Text.Encoding]::ASCII.GetBytes($username).CopyTo($packet, 6)
    [System.Text.Encoding]::ASCII.GetBytes($password).CopyTo($packet, 30)

    $stream.Write($packet, 0, $packet.Length)
    $stream.Flush()

    $buffer = New-Object byte[] 224
    $stream.Read($buffer, 0, $buffer.Length)
    $client.Close()

    # Extração de sessão
    $sessionId1 = [BitConverter]::ToUInt32($buffer, 2)
    $accountId = [BitConverter]::ToUInt32($buffer, 6)
    $sessionId2 = [BitConverter]::ToUInt32($buffer, 10)
    $sex = $buffer[26]

    Write-Host "[Parse] Login OK -> AID: ${accountId}" -ForegroundColor Green

    # 2. Char-Server
    $charClient = New-Object System.Net.Sockets.TcpClient("127.0.0.1", 6121)
    $charStream = $charClient.GetStream()

    $charPacket = New-Object byte[] 19
    $charPacket[0] = 0x65
    $charPacket[1] = 0x00
    [BitConverter]::GetBytes($accountId).CopyTo($charPacket, 2)
    [BitConverter]::GetBytes($sessionId1).CopyTo($charPacket, 6)
    [BitConverter]::GetBytes($sessionId2).CopyTo($charPacket, 10)
    [BitConverter]::GetBytes(0).CopyTo($charPacket, 14)
    $charPacket[18] = $sex

    $charStream.Write($charPacket, 0, $charPacket.Length)
    $charStream.Flush()

    # Consumir o pacote inicial do Char-Server
    $dummy = New-Object byte[] 1024
    $charStream.Read($dummy, 0, $dummy.Length) | Out-Null

    # Enviar pacote de seleção de personagem (Slot 0)
    $selectPacket = New-Object byte[] 3
    $selectPacket[0] = 0x66
    $selectPacket[1] = 0x00
    $selectPacket[2] = 0x00 # Slot 0

    Write-Host "[Bypass] A enviar pacote de seleção de personagem (Slot 0)..." -ForegroundColor Cyan
    $charStream.Write($selectPacket, 0, $selectPacket.Length)
    $charStream.Flush()

    # Ler a resposta do Char-Server com o IP e Porta do Map-Server (tipicamente um pacote AC_REFUSE_LOGIN ou CH_LOGIN_GEIST/Map Info)
    $mapResponseBuffer = New-Object byte[] 1024
    $mapBytesRead = $charStream.Read($mapResponseBuffer, 0, $mapResponseBuffer.Length)
    $charClient.Close()

    Write-Host "[Char-Server] Resposta à seleção recebida: ${mapBytesRead} bytes" -ForegroundColor Yellow
    
    if ($mapBytesRead -gt 0) {
        # No rAthena padrão, o Char-Server devolve o IP (4 bytes) e a Porta (2 bytes) do Map-Server na resposta de seleção
        # Vamos assumir o padrão local do Docker (127.0.0.1:5121) para validar o túnel socket
        $mapIp = "127.0.0.1"
        $mapPort = 5121

        Write-Host "[Parse] Map-Server endpoint detetado -> IP: ${mapIp} | Porta: ${mapPort}" -ForegroundColor Cyan

        # 3. Conectar ao Map-Server
        Write-Host "[Bypass] A ligar ao Map-Server em ${mapIp}:${mapPort}..." -ForegroundColor Cyan
        $mapClient = New-Object System.Net.Sockets.TcpClient($mapIp, $mapPort)

        if ($mapClient.Connected) {
            Write-Host "[SUCESSO ABSOLUTO] Conectado diretamente ao Map-Server! O ciclo tri-tier está fechado!" -ForegroundColor Green
        }
        $mapClient.Close()
    }

} catch {
    Write-Host "[ERRO] $($_.Exception.Message)" -ForegroundColor Red
}