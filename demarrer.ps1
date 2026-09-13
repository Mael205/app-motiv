# Lance le coach en fond : l'API, l'horloge, l'app construite et l'agent.
#
#   powershell -ExecutionPolicy Bypass -File demarrer.ps1            # lance ce qui manque
#   powershell -ExecutionPolicy Bypass -File demarrer.ps1 -Installer # + au démarrage de Windows
#   powershell -ExecutionPolicy Bypass -File demarrer.ps1 -Arreter   # coupe tout
#
# Relancer le script ne double rien : chaque morceau déjà en route est laissé tel
# quel. C'est ce qui permet de l'appeler à chaque ouverture de session sans se
# demander ce qui tourne encore.
#
# Les journaux vont dans %LOCALAPPDATA%\coach\logs, hors du dépôt et hors de
# OneDrive : quatre fichiers qui grossissent n'ont rien à faire dans une synchro.

param([switch]$Installer, [switch]$Arreter)

$ErrorActionPreference = 'Stop'
$racine = $PSScriptRoot
$api = Join-Path $racine 'coach-api'
$app = Join-Path $racine 'coach-app'
$agent = Join-Path $racine 'coach-agent'
$pythonw = Join-Path $api '.venv\Scripts\pythonw.exe'
$logs = Join-Path $env:LOCALAPPDATA 'coach\logs'
New-Item -ItemType Directory -Force $logs | Out-Null

# Chaque morceau est reconnu par un motif de sa ligne de commande.
$morceaux = @(
    @{ Nom = 'api';      Motif = '*manage.py*runserver*'; Exe = $pythonw; Dossier = $api
       Args = @('manage.py', 'runserver', '127.0.0.1:8000', '--noreload') }
    @{ Nom = 'horloge';  Motif = '*manage.py*tick*--loop*'; Exe = $pythonw; Dossier = $api
       Args = @('manage.py', 'tick', '--loop') }
    @{ Nom = 'app';      Motif = '*vite*preview*'; Exe = 'node'; Dossier = $app
       Args = @('node_modules/vite/bin/vite.js', 'preview', '--port', '4173', '--strictPort') }
    @{ Nom = 'agent';    Motif = '*coach-agent*agent.py*'; Exe = $pythonw; Dossier = $agent
       Args = @((Join-Path $agent 'agent.py'), '--quiet') }
)

function Trouver($motif) {
    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like $motif }
}

if ($Arreter) {
    foreach ($m in $morceaux) {
        foreach ($p in Trouver $m.Motif) {
            Stop-Process -Id $p.ProcessId -Force -Confirm:$false
            Write-Output "arrêté : $($m.Nom)"
        }
    }
    return
}

if ($Installer) {
    # Un raccourci dans le dossier Démarrage plutôt qu'une tâche planifiée :
    # « à l'ouverture de session » demande les droits administrateur, et rien
    # ici n'en a besoin — seul le service de blocage les a (coach-agent/README.md).
    $demarrage = [Environment]::GetFolderPath('Startup')
    $lien = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $demarrage 'Coach.lnk'))
    $lien.TargetPath = 'powershell.exe'
    $lien.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $lien.WorkingDirectory = $racine
    $lien.WindowStyle = 7
    $lien.Save()
    Write-Output "installé : $($lien.FullName)"
}

# L'app servie est la version construite. Si le code a bougé depuis, on
# reconstruit d'abord : sinon le coach tournerait des jours sur une version
# que plus personne n'a sous les yeux.
$construite = Join-Path $app 'dist\index.html'
$source = Get-ChildItem (Join-Path $app 'src') -Recurse -File |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not (Test-Path $construite) -or $source.LastWriteTime -gt (Get-Item $construite).LastWriteTime) {
    if (-not (Trouver '*vite*preview*')) {
        Write-Output 'construction de l''app…'
        # Par cmd et pas par `& npm *>` : PowerShell 5.1 change chaque ligne
        # d'erreur d'un exécutable en erreur PowerShell, et l'avertissement de
        # taille de Vite suffisait à arrêter le script avant qu'il lance quoi
        # que ce soit. Seul le code de sortie dit si la construction a échoué.
        $journal = Join-Path $logs 'build.log'
        $construction = Start-Process cmd.exe -ArgumentList '/d', '/c', "npm run build > `"$journal`" 2>&1" `
            -WorkingDirectory $app -WindowStyle Hidden -Wait -PassThru
        if ($construction.ExitCode -ne 0) {
            Write-Output "construction échouée (voir $journal) : on sert la version précédente"
        }
    }
}

foreach ($m in $morceaux) {
    if (Trouver $m.Motif) {
        Write-Output "déjà en route : $($m.Nom)"
        continue
    }
    Start-Process -FilePath $m.Exe -ArgumentList $m.Args -WorkingDirectory $m.Dossier `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logs "$($m.Nom).log") `
        -RedirectStandardError (Join-Path $logs "$($m.Nom).err.log")
    Write-Output "lancé : $($m.Nom)"
}

Write-Output 'Coach : http://localhost:4173'
