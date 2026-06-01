<#
.SYNOPSIS
    Очистка временных файлов и настройка производительности Windows.
.DESCRIPTION
    Этот скрипт удаляет временные файлы из стандартных папок, очищает корзину,
    сбрасывает DNS-кэш и переключает план питания на максимально производительный.
.NOTES
    Запустите PowerShell от имени администратора для полного доступа к системным
    временным папкам и настройке плана питания.
#>

function Test-Admin {
    $currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Remove-TempFiles {
    param(
        [Parameter(Mandatory=$true)] [string[]]$Paths
n    )

    foreach ($path in $Paths) {
        if (-not (Test-Path $path)) {
            Write-Verbose "Путь не найден: $path"
            continue
        }

        Write-Host "Очищаю: $path"
        try {
            Get-ChildItem -Path $path -Force -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
                try {
                    if ($_.PSIsContainer) {
                        Remove-Item -LiteralPath $_.FullName -Force -Recurse -ErrorAction SilentlyContinue
                    } else {
                        Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
                    }
                } catch {
                    # игнорируем файлы, занятые системой
                }
            }
        } catch {
            Write-Warning "Не удалось очистить: $path"
        }
    }
}

function Clear-RecycleBin {
    Write-Host "Очищаю корзину..."
    try {
        $shell = New-Object -ComObject Shell.Application
        $recycle = $shell.Namespace(0x000a)
        $items = $recycle.Items()
        if ($items.Count -gt 0) {
            $recycle.InvokeVerb("Empty Recycle &Bin")
            Write-Host "Корзина очищена."
        } else {
            Write-Host "Корзина пуста."
        }
    } catch {
        Write-Warning "Не удалось очистить корзину через COM."
    }
}

function Set-HighPerformancePowerPlan {
    Write-Host "Проверяю и устанавливаю наиболее производительный план питания..."
    try {
        $plans = powercfg /L 2>&1 | Select-String -Pattern "([A-F0-9\-]{36})\s+\((.+)\)\s*(\*)?"
        if (-not $plans) {
            Write-Warning "Не удалось получить список планов питания."
            return
        }

        $selectedPlan = $null
        foreach ($line in $plans) {
            if ($line.Line -match "([A-F0-9\-]{36})\s+\((.+)\)") {
                $guid = $matches[1]
                $name = $matches[2].Trim()
                if ($name -match 'Ultimate Performance') {
                    $selectedPlan = $guid
                    break
                }
                if (-not $selectedPlan -and $name -match 'High performance') {
                    $selectedPlan = $guid
                }
            }
        }

        if ($selectedPlan) {
            powercfg /S $selectedPlan | Out-Null
            Write-Host "Установлен план питания: $selectedPlan"
        } else {
            Write-Warning "Не найден подходящий план питания Ultimate Performance или High performance."
        }
    } catch {
        Write-Warning "Ошибка при установке плана питания: $_"
    }
}

function Flush-Dns {
    Write-Host "Сбрасываю DNS-кеш..."
    try {
        ipconfig /flushdns | Out-Null
        Write-Host "DNS-кеш сброшен."
    } catch {
        Write-Warning "Не удалось сбросить DNS-кеш."
    }
}

Write-Host "=== Очистка мусора и оптимизация производительности Windows ===" -ForegroundColor Cyan

if (-not (Test-Admin)) {
    Write-Warning "Рекомендуется запускать этот скрипт от имени администратора для полной очистки и настройки."
}

$commonTempPaths = @(
    "$env:TEMP",
    "$env:TMP",
    "$env:USERPROFILE\AppData\Local\Temp"
)

if (Test-Admin) {
    $commonTempPaths += "C:\Windows\Temp"
}

Remove-TempFiles -Paths $commonTempPaths
Clear-RecycleBin
Flush-Dns
Set-HighPerformancePowerPlan

Write-Host "Готово. Рекомендуется перезагрузить систему, чтобы завершить очистку и применить настройки." -ForegroundColor Green
