$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech

try {
    $culture = [System.Globalization.CultureInfo]::GetCultureInfo('ru-RU')
    $recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)
} catch {
    # Если в Windows нет русского пакета распознавания, используем доступный.
    $recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine
}

$recognizer.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
$recognizer.SetInputToDefaultAudioDevice()
$result = $recognizer.Recognize([TimeSpan]::FromSeconds(12))
if ($null -ne $result) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $result.Text
}
