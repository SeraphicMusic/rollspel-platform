# Quick Gemini image API test - run this in your PowerShell terminal
# Usage: .\Test-GeminiApi.ps1

$ErrorActionPreference = "Stop"

$key = $env:GEMINI_API_KEY
if (-not $key) {
    Write-Host "ERROR: Set API key first: " -ForegroundColor Red -NoNewline
    Write-Host '$env:GEMINI_API_KEY = "AIza..."'
    return
}

$model = "gemini-2.5-flash-image"
$uri = "https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${key}"

$body = @{
    contents = @(@{
        parts = @(@{ text = "A simple orc warrior portrait, dark fantasy style" })
    })
    generationConfig = @{
        responseModalities = @("IMAGE")
    }
} | ConvertTo-Json -Depth 8

Write-Host "Testing Gemini image generation..." -ForegroundColor Cyan
Write-Host "Model: $model"
Write-Host "Endpoint: $($uri -replace $key, '***')"
Write-Host ""

try {
    Write-Host "Calling API (may take 30-60s for image generation)..."
    $resp = Invoke-RestMethod -Method Post -Uri $uri `
        -ContentType "application/json; charset=utf-8" `
        -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) `
        -TimeoutSec 120

    Write-Host "API returned successfully!" -ForegroundColor Green

    if ($resp.candidates) {
        $part = $resp.candidates[0].content.parts[0]
        if ($part.inlineData -and $part.inlineData.data) {
            $mime = $part.inlineData.mimeType
            $dataLen = $part.inlineData.data.Length
            Write-Host "Got image: mime=$mime, base64 length=$dataLen" -ForegroundColor Green

            # Save the test image
            $ext = if ($mime -eq "image/png") { "png" } elseif ($mime -eq "image/jpeg") { "jpg" } else { "webp" }
            $outPath = "C:\Users\kalwinde\Downloads\gemini-test-orc.$ext"
            $bytes = [Convert]::FromBase64String($part.inlineData.data)
            [IO.File]::WriteAllBytes($outPath, $bytes)
            Write-Host "Saved test image: $outPath" -ForegroundColor Green
        }
        else {
            Write-Host "Response has candidates but no inlineData:" -ForegroundColor Yellow
            $resp.candidates[0].content.parts | ForEach-Object {
                $_ | ConvertTo-Json -Depth 3
            }
        }
    }
    else {
        Write-Host "No candidates in response:" -ForegroundColor Yellow
        $resp | ConvertTo-Json -Depth 4
    }
}
catch {
    Write-Host "API ERROR: $($_.Exception.Message)" -ForegroundColor Red

    # Try to get detailed error body
    try {
        $stream = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($stream)
        $reader.BaseStream.Position = 0
        $errBody = $reader.ReadToEnd()
        $reader.Close()
        Write-Host "Error detail:" -ForegroundColor Red
        Write-Host $errBody
    }
    catch {
        Write-Host "(Could not read error body)" -ForegroundColor DarkYellow
    }
}
