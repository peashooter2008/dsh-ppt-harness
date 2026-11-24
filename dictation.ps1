$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Speech
$info = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() |
    Where-Object { $_.Culture.Name -eq 'zh-CN' } | Select-Object -First 1
if ($null -eq $info) { exit 3 }
$engine = [System.Speech.Recognition.SpeechRecognitionEngine]::new($info)
$audio = [IO.MemoryStream]::new()
try {
    [Console]::OpenStandardInput().CopyTo($audio)
    $audio.Position = 0
    $engine.LoadGrammar([System.Speech.Recognition.DictationGrammar]::new())
    $engine.SetInputToWaveStream($audio)
    $lines = [Collections.Generic.List[string]]::new()
    while ($true) {
        try { $phrase = $engine.Recognize() }
        catch [InvalidOperationException] {
            if ($audio.Position -ge $audio.Length) { break }
            throw
        }
        if ($null -eq $phrase) { break }
        if ($phrase.Text) { $lines.Add($phrase.Text) }
    }
    [Console]::Write(($lines -join [char]0x3002))
} finally {
    $engine.Dispose()
    $audio.Dispose()
}
