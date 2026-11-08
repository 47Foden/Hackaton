$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$sampleDirectory = Join-Path $repoRoot 'recordings/whisper-benchmark'
New-Item -ItemType Directory -Path $sampleDirectory -Force | Out-Null

$samples = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'korean_samples.json') -Encoding utf8 -Raw | ConvertFrom-Json
$voice = New-Object -ComObject SAPI.SpVoice
$voices = $voice.GetVoices('Language=412')
if ($voices.Count -eq 0) { throw 'A Korean Windows SAPI voice is required.' }
$voice.Voice = $voices.Item(0)

foreach ($sample in $samples) {
    $stream = New-Object -ComObject SAPI.SpFileStream
    $stream.Format.Type = 18 # SAFT16kHz16BitMono
    $stream.Open((Join-Path $sampleDirectory "$($sample.id).wav"), 3, $false) # SSFMCreateForWrite
    try {
        $voice.AudioOutputStream = $stream
        $voice.Speak($sample.reference) | Out-Null
    } finally {
        $stream.Close()
    }
}

Write-Output "Generated $($samples.Count) samples with $($voice.Voice.GetDescription())."
