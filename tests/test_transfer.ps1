# ============================================================
# Script de prueba: crear transferencia interbancaria
# ============================================================

# ---------- CONFIGURACIÓN ----------
$TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJCQU5LX0EiLCJzY29wZXMiOlsidHJhbnNmZXJzOndyaXRlIiwidHJhbnNmZXJzOnJlYWQiXSwiaWF0IjoxNzk0MDMzMDY0LCJleHAiOjE3OTQwMzY2NjR9.PSLyj2-z4QoD39yG5SO4geXJjfWFsh5XNZGQfAZKjvs"    # ← Reemplaza con el access_token que obtuviste
$BANK_ID = "BANK_A"
$BANK_SECRET = "bank_a_secret"
$HUB_URL = "http://localhost:8000/api/v1/transfers"
$idempotencyKey = "550e8400-e29b-41d4-a716-446655440000" 

# ---------- BODY ----------
$bodyObj = [ordered]@{
    origin_bank_id      = "BANK_A"
    destination_bank_id = "DINOBIT"
    amount              = "1500.00"
    currency            = "PEN"
    concept             = "Pago factura #00123"
    #client_transfer_id  = "BNK-A-2026-000043"
    client_transfer_id  = "BNK-A-TEST-IDEMPOTENCIA"
    priority            = "NORMAL"
    metadata            = [ordered]@{
        invoice_id   = "INV-00123"
        customer_ref = "CUST-9981"
    }
}
$bodyJson = $bodyObj | ConvertTo-Json -Depth 10 -Compress

# Escribir body a archivo temporal (evita problemas de escape de PowerShell)
$bodyFile = Join-Path $PWD "body_tmp.json"
[System.IO.File]::WriteAllText($bodyFile, $bodyJson, [System.Text.UTF8Encoding]::new($false))

# ---------- TIMESTAMP ----------
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

# ---------- FIRMA HMAC ----------
# Se firma: "<timestamp>.<body>"
$message = "$timestamp.$bodyJson"
$messageBytes = [System.Text.Encoding]::UTF8.GetBytes($message)

$hmac = [System.Security.Cryptography.HMACSHA256]::new(
    [System.Text.Encoding]::UTF8.GetBytes($BANK_SECRET)
)
$signatureBytes = $hmac.ComputeHash($messageBytes)
$signature = [System.BitConverter]::ToString($signatureBytes).Replace("-", "").ToLower()

# ---------- IDEMPOTENCY KEY ----------
# Descomenta para usar key fija (para probar idempotencia)
# $idempotencyKey = "550e8400-e29b-41d4-a716-446655440000"
$idempotencyKey = [guid]::NewGuid().ToString()

# ---------- MOSTRAR INFO ----------
Write-Host "=== Configuracion ===" -ForegroundColor Cyan
Write-Host "Timestamp:        $timestamp"
Write-Host "Idempotency-Key:  $idempotencyKey"
Write-Host "Signature:        $signature"
Write-Host ""
Write-Host "=== Body ===" -ForegroundColor Cyan
Write-Host $bodyJson
Write-Host ""
Write-Host "=== POST /api/v1/transfers ===" -ForegroundColor Cyan

# ---------- REQUEST ----------
$response = curl.exe -s -X POST $HUB_URL `
    -H "Authorization: Bearer $TOKEN" `
    -H "Content-Type: application/json" `
    -H "X-Bank-Id: $BANK_ID" `
    -H "X-Idempotency-Key: $idempotencyKey" `
    -H "X-Timestamp: $timestamp" `
    -H "X-Signature: $signature" `
    --data-binary "@$bodyFile"

# ---------- MOSTRAR RESPUESTA ----------
Write-Host ""
Write-Host "=== Respuesta ===" -ForegroundColor Cyan
Write-Host $response

# ---------- LIMPIAR ----------
Remove-Item $bodyFile -ErrorAction SilentlyContinue