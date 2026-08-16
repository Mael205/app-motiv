# Redemarre l'API de developpement en tuant d'abord TOUTES les instances.
#
# Existe parce que le piege s'est referme trois fois : sous Windows, `pkill` du
# shell Git Bash ne tue pas les processus Python, et plusieurs runserver
# peuvent ecouter le meme port grace a SO_REUSEADDR. Celui qui repond est alors
# le plus ancien — donc du code perime — et on debogue une version qui n'existe
# plus dans les fichiers.
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*runserver*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force; "arrete $($_.ProcessId)" }

Start-Sleep -Seconds 2
$reste = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*runserver*' })
if ($reste.Count) { throw "$($reste.Count) serveur(s) toujours vivant(s)" }

Push-Location "$PSScriptRoot\..\..\coach-api"
$env:COACH_AI_ENABLED = "0"
Start-Process -FilePath ".venv\Scripts\python.exe" `
  -ArgumentList "manage.py","runserver","8000","--noreload" `
  -WindowStyle Hidden
Pop-Location

Start-Sleep -Seconds 5
(Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing).StatusCode
