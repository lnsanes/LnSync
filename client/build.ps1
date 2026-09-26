$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo = Split-Path -Parent $Root
$Jdk = $env:JAVA_HOME
$javacProbe = if ($Jdk) { Join-Path $Jdk "bin\javac.exe" } else { "" }
if (-not $Jdk -or -not (Test-Path $javacProbe)) {
    $candidates = @(
        "C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot",
        "C:\Program Files\Eclipse Adoptium\jdk-17*",
        "C:\Program Files\Java\jdk-17*",
        "C:\Program Files\Microsoft\jdk-17*"
    )
    foreach ($pattern in $candidates) {
        $match = Get-Item $pattern -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($match -and (Test-Path (Join-Path $match.FullName "bin\javac.exe"))) {
            $Jdk = $match.FullName
            break
        }
    }
}
if (-not $Jdk -or -not (Test-Path (Join-Path $Jdk "bin\javac.exe"))) {
    throw "JDK 17+ required (set JAVA_HOME)"
}

$Javac = Join-Path $Jdk "bin\javac.exe"
$JarTool = Join-Path $Jdk "bin\jar.exe"
$Out = Join-Path $Root "out"
$Dist = Join-Path $Repo "dist\client"
$Manifest = Join-Path $Root "resources\META-INF\MANIFEST.MF"

if (Test-Path $Out) { Remove-Item $Out -Recurse -Force }
New-Item -ItemType Directory -Path $Out, $Dist -Force | Out-Null

$sources = Get-ChildItem -Path (Join-Path $Root "src") -Filter *.java -Recurse | ForEach-Object { $_.FullName }
& $Javac -encoding UTF-8 --release 17 -d $Out @sources
if ($LASTEXITCODE -ne 0) { throw "javac failed" }

function Remove-StubPackages([string]$stage) {
    foreach ($rel in @(
            "net\minecraftforge",
            "net\neoforged",
            "net\fabricmc",
            "cpw\mods",
            "org\quiltmc"
        )) {
        $path = Join-Path $stage $rel
        if (Test-Path $path) { Remove-Item $path -Recurse -Force }
    }
    foreach ($empty in @("net", "cpw", "org")) {
        $path = Join-Path $stage $empty
        if ((Test-Path $path) -and -not (Get-ChildItem $path -Recurse -File -ErrorAction SilentlyContinue)) {
            Remove-Item $path -Recurse -Force
        }
    }
}

function New-LoaderJar {
    param(
        [string]$Loader,
        [string]$JarName,
        [string[]]$KeepClasses,
        [string[]]$DropClasses
    )
    $stage = Join-Path $Root ("out-" + $Loader)
    if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    Copy-Item (Join-Path $Out "*") $stage -Recurse -Force

    $pkg = Join-Path $stage "com\lnsanes\lnsync"
    foreach ($name in $DropClasses) {
        Get-ChildItem $pkg -Filter ($name + "*") -ErrorAction SilentlyContinue | Remove-Item -Force
    }
    foreach ($name in $KeepClasses) {
        $file = Join-Path $pkg ($name + ".class")
        if (-not (Test-Path $file)) { throw "missing class $name for $Loader" }
    }

    $loaderRes = Join-Path $Root "resources\loaders\$Loader"
    if (-not (Test-Path $loaderRes)) { throw "missing resources for $Loader" }
    Copy-Item (Join-Path $loaderRes "*") $stage -Recurse -Force

    Remove-StubPackages $stage

    $jarFile = Join-Path $Dist $JarName
    if (Test-Path $jarFile) { Remove-Item $jarFile -Force }
    Push-Location $stage
    try {
        & $JarTool --create --file $jarFile --manifest $Manifest .
        if ($LASTEXITCODE -ne 0) { throw "jar failed for $Loader" }
    } finally {
        Pop-Location
    }
    Remove-Item $stage -Recurse -Force
    Write-Host "Built $jarFile"
}

# Shared core stays; drop unused loader entrypoints per jar.
$allEntries = @(
    "LnSyncMod",
    "LnSyncNeoForgeMod",
    "LnSyncLaunchService",
    "LnSyncFabricPreLaunch",
    "LnSyncQuiltPreLaunch"
)

New-LoaderJar -Loader "forge" -JarName "lnsync-forge.jar" `
    -KeepClasses @("LnSyncMod", "LnSyncLaunchService") `
    -DropClasses @("LnSyncNeoForgeMod", "LnSyncFabricPreLaunch", "LnSyncQuiltPreLaunch")

New-LoaderJar -Loader "neoforge" -JarName "lnsync-neoforge.jar" `
    -KeepClasses @("LnSyncNeoForgeMod", "LnSyncLaunchService") `
    -DropClasses @("LnSyncMod", "LnSyncFabricPreLaunch", "LnSyncQuiltPreLaunch")

New-LoaderJar -Loader "fabric" -JarName "lnsync-fabric.jar" `
    -KeepClasses @("LnSyncFabricPreLaunch") `
    -DropClasses @("LnSyncMod", "LnSyncNeoForgeMod", "LnSyncLaunchService", "LnSyncQuiltPreLaunch")

New-LoaderJar -Loader "quilt" -JarName "lnsync-quilt.jar" `
    -KeepClasses @("LnSyncQuiltPreLaunch") `
    -DropClasses @("LnSyncMod", "LnSyncNeoForgeMod", "LnSyncLaunchService", "LnSyncFabricPreLaunch")

# Universal: all entrypoints + all loader metadata in one jar.
$uniStage = Join-Path $Root "out-universal"
if (Test-Path $uniStage) { Remove-Item $uniStage -Recurse -Force }
New-Item -ItemType Directory -Path $uniStage -Force | Out-Null
Copy-Item (Join-Path $Out "*") $uniStage -Recurse -Force
foreach ($loader in @("forge", "neoforge", "fabric", "quilt")) {
    Copy-Item (Join-Path $Root "resources\loaders\$loader\*") $uniStage -Recurse -Force
}
Remove-StubPackages $uniStage
$uniJar = Join-Path $Dist "lnsync-universal.jar"
if (Test-Path $uniJar) { Remove-Item $uniJar -Force }
Push-Location $uniStage
try {
    & $JarTool --create --file $uniJar --manifest $Manifest .
    if ($LASTEXITCODE -ne 0) { throw "jar failed for universal" }
} finally {
    Pop-Location
}
Remove-Item $uniStage -Recurse -Force
Copy-Item $uniJar (Join-Path $Dist "lnsync.jar") -Force
Write-Host "Built $uniJar"
Write-Host "Built $(Join-Path $Dist 'lnsync.jar') (alias of universal)"

Copy-Item (Join-Path $Root "lnsync.toml.example") (Join-Path $Dist "lnsync.toml.example") -Force
Copy-Item (Join-Path $Root "CLIENT-README.txt") (Join-Path $Dist "CLIENT-README.txt") -Force
$zh = Join-Path $Root ([char]0x4F7F + [char]0x7528 + [char]0x8BF4 + [char]0x660E + ".txt")
if (Test-Path $zh) {
    Copy-Item $zh (Join-Path $Dist ([IO.Path]::GetFileName($zh))) -Force
}

Get-ChildItem $Dist -Filter "lnsync-client.jar" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem $Dist -Filter "sync-client.bat" -ErrorAction SilentlyContinue | Remove-Item -Force
