function Generate-Portraits {
<#
.SYNOPSIS
  Bulk-generate RPG character/monster portraits with Google Gemini image generation.

.PARAMETER StylePrompt
  Art direction prompt controlling rendering style, palette, lighting, etc.

.PARAMETER Subjects
  Array of monster descriptions to generate portraits for.

.PARAMETER ApiKey
  Google Gemini API key. Prefer using $env:GEMINI_API_KEY.

.PARAMETER OutDir
  Output directory. Default: C:\dnd\public\Portraits\Monster

.PARAMETER AspectRatio
  Image aspect ratio. Default: 1:1

.PARAMETER ImageSize
  Image resolution: 1K, 2K, 4K. Default: 1K

.PARAMETER Model
  Gemini model to use. Default: gemini-2.5-flash-image

.PARAMETER ImagesPerSubject
  Number of images to generate per subject (1-4). Default: 1

.PARAMETER DelaySeconds
  Pause between API calls to avoid rate limiting. Default: 2

.EXAMPLE
  $style = "Gritty dark fantasy monster portrait, Drakar och Demoner style."
  $subjects = @("Orc Warrior, rusty chainmail", "Cave Troll, mossy skin")
  Generate-Portraits -StylePrompt $style -Subjects $subjects -ApiKey $env:GEMINI_API_KEY

.EXAMPLE
  # Read subjects from file
  Generate-Portraits -StylePrompt $style -Subjects $subjects -ApiKey $env:GEMINI_API_KEY -OutDir "C:\Temp\Monsters"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$StylePrompt,

    [Parameter(Mandatory)]
    [string]$ApiKey,

    [Parameter(Mandatory)]
    [string[]]$Subjects,

    [Parameter(Mandatory)]
    [string]$OutDir,

    [ValidateSet("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9")]
    [string]$AspectRatio = "1:1",

    [ValidateSet("1K", "2K", "4K")]
    [string]$ImageSize = "1K",

    [string]$Model = "gemini-2.5-flash-image",

    [ValidateRange(1, 4)]
    [int]$ImagesPerSubject = 1,

    [ValidateRange(0, 30)]
    [int]$DelaySeconds = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-Slug {
    param([Parameter(Mandatory)][string]$Text)
    $t = $Text.ToLowerInvariant()
    # Transliterate Swedish/Nordic characters to ASCII
    $t = $t -replace 'å', 'a' -replace 'ä', 'a' -replace 'ö', 'o'
    $t = $t -replace 'é', 'e' -replace 'ü', 'u' -replace 'ø', 'o' -replace 'æ', 'ae'
    $t = $t -replace '[^\p{IsBasicLatin}]+', '-'
    $t = $t -replace '[^a-z0-9]+', '-'
    $t = $t.Trim('-')
    if ($t.Length -gt 80) { $t = $t.Substring(0, 80).Trim('-') }
    if ([string]::IsNullOrWhiteSpace($t)) { $t = "subject" }
    return $t
}

function Invoke-GeminiImageGenerate {
    param(
        [Parameter(Mandatory)][string]$Prompt,
        [Parameter(Mandatory)][string]$Key,
        [Parameter(Mandatory)][string]$ModelName,
        [Parameter(Mandatory)][string]$Ratio,
        [Parameter(Mandatory)][string]$Size
    )

    $uri = "https://generativelanguage.googleapis.com/v1beta/models/${ModelName}:generateContent?key=${Key}"

    $body = @{
        contents = @(@{
            parts = @(@{ text = $Prompt })
        })
        generationConfig = @{
            responseModalities = @("IMAGE")
        }
    } | ConvertTo-Json -Depth 8

    $maxAttempts = 5
    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        try {
            $resp = Invoke-RestMethod -Method Post -Uri $uri `
                -ContentType "application/json; charset=utf-8" `
                -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) `
                -TimeoutSec 300
            return $resp
        }
        catch {
            $msg = $_.Exception.Message
            # Extract response body for detailed error info
            $detail = ""
            try {
                $stream = $_.Exception.Response.GetResponseStream()
                $reader = New-Object System.IO.StreamReader($stream)
                $reader.BaseStream.Position = 0
                $detail = $reader.ReadToEnd()
                $reader.Close()
            } catch {}

            if ($attempt -eq $maxAttempts) {
                if ($detail) { Write-Warning "API error detail: $detail" }
                throw
            }

            $sleep = [Math]::Min(30, [Math]::Pow(2, $attempt))
            Write-Warning "Gemini call failed (attempt $attempt/$maxAttempts): $msg"
            if ($detail) { Write-Warning "   Detail: $detail" }
            Write-Warning "Retrying in $sleep seconds..."
            Start-Sleep -Seconds $sleep
        }
    }
}

# Validate subjects
$cleanSubjects = @($Subjects | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object { $_.Trim() })
if ($cleanSubjects.Count -eq 0) {
    throw "No valid subjects provided."
}

# Ensure output directory
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

Write-Host "Model: $Model | Aspect: $AspectRatio | Size: $ImageSize"
Write-Host "Generating $ImagesPerSubject image(s) per subject to: $OutDir"
Write-Host "Subjects: $($cleanSubjects.Count)"
Write-Host ""

$successCount = 0
$failCount = 0

foreach ($subject in $cleanSubjects) {

    # Strip book prefix from prompt (only used for filename)
    $promptSubject = if ($subject -match '^\s*[^|]+\|(.+)$') { $Matches[1].Trim() } else { $subject }

    $fullPrompt = @"
$StylePrompt

MOTIV:
$promptSubject

Constraints:
- Portrait suitable for a tabletop RPG monster token/entry (no text, no watermark, no frame).
- Readable silhouette, clear facial features, strong class/creature readability.
- Neutral/soft background, not distracting.
"@

    Write-Host "==> $subject"

    for ($imgIdx = 1; $imgIdx -le $ImagesPerSubject; $imgIdx++) {

        try {
            $resp = Invoke-GeminiImageGenerate -Prompt $fullPrompt -Key $ApiKey -ModelName $Model -Ratio $AspectRatio -Size $ImageSize
        }
        catch {
            Write-Warning "   FAILED after all retries: $($_.Exception.Message)"
            $failCount++
            continue
        }

        # Extract base64 image from response
        $saved = $false
        if ($resp.PSObject.Properties['candidates']) {
            foreach ($candidate in $resp.candidates) {
                if (-not $candidate.PSObject.Properties['content']) { continue }
                if (-not $candidate.content.PSObject.Properties['parts']) { continue }
                foreach ($part in $candidate.content.parts) {
                    if ($part.PSObject.Properties['inlineData'] -and $part.inlineData.PSObject.Properties['data']) {
                        $mime = $part.inlineData.mimeType
                        $ext = switch ($mime) {
                            "image/png"  { "png" }
                            "image/jpeg" { "jpg" }
                            "image/webp" { "webp" }
                            default      { "png" }
                        }

                        # Parse "BOOK|Creature, description..." format
                        if ($subject -match '^\s*([^|]+)\|(.+)$') {
                            $bookNum = $Matches[1].Trim().ToLowerInvariant()
                            $descPart = $Matches[2].Trim()
                        } else {
                            $bookNum = ""
                            $descPart = $subject
                        }
                        $creatureName = ($descPart -split ',')[0].Trim()
                        $slug = New-Slug -Text $creatureName
                        if ($bookNum) { $slug = "${bookNum}-${slug}" }
                        $fileName = "${slug}.${ext}"
                        $outPath = Join-Path $OutDir $fileName

                        $bytes = [Convert]::FromBase64String($part.inlineData.data)
                        [IO.File]::WriteAllBytes($outPath, $bytes)
                        Write-Host "   Saved: $outPath"
                        $saved = $true
                        $successCount++
                        break
                    }
                }
                if ($saved) { break }
            }
        }

        if (-not $saved) {
            Write-Warning "   No image data returned for: $subject (image $imgIdx)"
            if ($resp) {
                # Log the response structure for debugging
                $respJson = $resp | ConvertTo-Json -Depth 5 -Compress
                if ($respJson.Length -gt 500) { $respJson = $respJson.Substring(0, 500) + "..." }
                Write-Warning "   Response: $respJson"
            }
            $failCount++
        }

        # Delay between individual image requests
        if ($DelaySeconds -gt 0 -and ($imgIdx -lt $ImagesPerSubject -or $subject -ne $cleanSubjects[-1])) {
            Start-Sleep -Seconds $DelaySeconds
        }
    }

    Write-Host ""
}

Write-Host "Done. Success: $successCount | Failed: $failCount"

}

# ─── Example usage ───────────────────────────────────────────

$ApiKey = $env:GEMINI_API_KEY
if (-not $ApiKey) {
    Write-Error "Set GEMINI_API_KEY environment variable first: `$env:GEMINI_API_KEY = 'AIza...'"
    return
}

$style = @"
Gritty hand-painted dark fantasy monster portrait mode.
Classic Swedish tabletop RPG vibe (Drakar och Demoner).
Textured brush strokes, natural imperfections, believable materials.
Moody low-key lighting, muted earthy palette, high readability.
"@

$subjects = @(
    "I|Erbolsus Ödvinsson, kort och småfet erebosisk handelsman i femtioårsåldern, klädd i dyrbara österländska kläder och tunga guldkedjor, förtvivlat ansiktsuttryck"
    "I|Bhismall, muskulös efarisk slav med likgiltig blick, bär en enkel klädnad och håller ett långt spjut, stor kroksabel i bältet"
    "I|Abdhull, muskulös efarisk slav med vaksam blick, bär en enkel klädnad och håller ett långt spjut, stor kroksabel i bältet"
    "I|Valentin Hinkare, högmodig adelsman med kylig blick och välvårdat utseende, bär en dyrbar sammetstunika och en stor sigillring"
    "I|Steinar Rödnäbb, antropomorf vit anka i sjömanskläder, vaksam och nervös blick, befinner sig i ett stökigt hamnkontor"
    "I|Erminkus Ödvinsson, tolvårig pojke med ljust rufsigt hår och smutsigt ansikte, bär trasiga men tidigare fina kläder, rädd blick"
    "I|Lintott, liten och senig tjuv med kvicka rörelser, klädd i mörka slitna kläder, har ett lurigt leende"
    "I|Dyvik, stor och kraftig vakt hos handelshuset Hinkare, klädd i läderharnesk med husets emblem, bär en tung stridsklubba"
    "I|Amiral Raggaldo, respektingivande äldre man med grått hår och väderbitet ansikte, bär en amiralsuniform dekorerad med guld och medaljer"
    "I|Nithard Silverskiöld, kraftig riddare i skinande helrustning, bär en mantel med ett adligt vapensköldsmotiv, håller i ett svärdshjälte"
    "I|Erasmus Ödvinsson, ung man i tjugoårsåldern med ädelt ansikte, klädd i praktiska men eleganta resekläder, ser bekymrad ut"
    "I|Bardak Tveskägg, man med ett karaktäristiskt delat skägg, klädd som en välbärgad borgare, har en vaksam och svekfull blick"
    "I|Torgunn den Sköna, vacker kvinna i medelåldern med sorgsen blick, klädd i eleganta klänningar av finaste siden"
    "I|Hertigen av Yttersol, myndig adelsman i zorakisk hovdräkt, bär en tung pälsbrämad mantel och en gyllene kedja, sträng blick"
    "I|Baron Kvistehål, landsortsadelsman med rödbrusigt ansikte, klädd i jaktkläder av läder och ylle, bär en jaktkniv i bältet"
    "I|Hamnvakt i Nohstril, kraftig man i läderharnesk och öppen hjälm, bär en hillebard och en kort tunika med stadens emblem"
    "I|Erebosisk lönnmördare, maskerad gestalt klädd helt i svart och mörkblått, smidig kroppsbyggnad, håller en smal dolk"
    "I|Balking, en grovhuggen och ärrad sjöman, kapten på ett mindre handelsfartyg, bär en sliten kaptensrock och har en barsk röst"
    "I|Kaptenen på Gyllene Hinden, auktoritär man i förnäm sjömansuniform, bär en bredbrättad hatt och blickar ut över däcket"
    "I|Säkerhetsman, mager man i prydliga men enkla kläder, håller i ett skrivdon och ett pergament, har en noggrann blick"
)

Generate-Portraits -StylePrompt $style -Subjects $subjects -ApiKey $ApiKey -OutDir "C:\Users\kalwinde\Downloads\Rollspel Porträtt"
