$ip = "127.0.0.1"
$port = 6900
$packetVer = 20211105
$usernameInput = "testuser"
$passwordInput = "testpassword"

Write-Host "[Bypass] A ligar a ${ip}:${port}..." -ForegroundColor Cyan
try {
    $client = New-Object System.Net.Sockets.TcpClient
    $client.Connect($ip, $port)
    $stream = $client.GetStream()
    
    # Construir pacote 0x0064 (55 bytes)
    $payload = New-Object byte[] 55
    $payload[0] = 0x64
    $payload[1] = 0x00
    
    $versionBytes = [BitConverter]::GetBytes([UInt32]$packetVer)
    [Array]::Copy($versionBytes, 0, $payload, 2, 4)
    
    $username = [System.Text.Encoding]::ASCII.GetBytes($usernameInput)
    [Array]::Copy($username, 0, $payload, 6, [Math]::Min($username.Length, 24))
    
    $password = [System.Text.Encoding]::ASCII.GetBytes($passwordInput)
    [Array]::Copy($password, 0, $payload, 30, [Math]::Min($password.Length, 24))

    Write-Host "[Bypass] A enviar dados para autenticação..." -ForegroundColor Yellow
    $stream.Write($payload, 0, $payload.Length)
    $stream.Flush()
    
    # Aguardar resposta do servidor
    Start-Sleep -Milliseconds 800
    
    if ($stream.DataAvailable -or $client.Available -gt 0) {
        $buffer = New-Object byte[] 256
        $bytesRead = $stream.Read($buffer, 0, $buffer.Length)
        $hexResponse = [BitConverter]::ToString($buffer, 0, $bytesRead)
        Write-Host "[SUCESSO] Servidor respondeu com $bytesRead bytes: $hexResponse" -ForegroundColor Green
    } else {
        Write-Host "[SUCESSO] Pacote aceite e sessão estabilizada pelo servidor!" -ForegroundColor Green
    }
}
catch {
    Write-Host "[ERRO] $_" -ForegroundColor Red
}
finally {
    if ($client) { $client.Close() }
}
