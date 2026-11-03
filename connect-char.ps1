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

    Write-Host "[Bypass] A enviar dados de autenticação..." -ForegroundColor Yellow
    $stream.Write($packet, 0, $packet.Length)
    $stream.Flush()

    # 2. Ler a resposta de 224 bytes
    $buffer = New-Object byte[] 224
    $bytesRead = $stream.Read($buffer, 0, $buffer.Length)
    $client.Close()

    if ($bytesRead -eq 224) {
        Write-Host "[SUCESSO] Resposta de 224 bytes capturada do Login-Server!" -ForegroundColor Green

        # 3. Extrair IP e Porta do Char-Server do payload binário (offsets padrão do rAthena)
        $charIp = "$($buffer[58]).$($buffer[59]).$($buffer[60]).$($buffer[61])"
        $charPort = [BitConverter]::ToUInt16($buffer, 62)

        Write-Host "[Parse] Char-Server detetado -> IP: ${charIp} | Porta: ${charPort}" -ForegroundColor Cyan

        # 4. Conectar ao Char-Server (Porta 6121)
        Write-Host "[Bypass] A ligar ao Char-Server em ${charIp}:${charPort}..." -ForegroundColor Cyan
        $charClient = New-Object System.Net.Sockets.TcpClient($charIp, $charPort)

        if ($charClient.Connected) {
            Write-Host "[SUCESSO ABSOLUTO] Conectado com sucesso ao Char-Server!" -ForegroundColor Green
        }
        
        $charClient.Close()
    } else {
        Write-Host "[ERRO] O servidor respondeu com um tamanho inesperado: $bytesRead bytes." -ForegroundColor Red
    }

} catch {
    Write-Host "[ERRO DE REDE] $($_.Exception.Message)" -ForegroundColor Red
}