# Monitor Sistemi

Bu proje, ekran görüntüleri alma, klavye etkinliklerini kaydetme ve sistem ses kaydı yapma yeteneklerine sahip bir izleme sistemidir.

## Bileşenler

1. **monitor.py** - Ana izleme sistemi. Ekran görüntüleri alma, tuş vuruşlarını kaydetme, fare hareketlerini izleme ve pano değişikliklerini takip etme işlevlerini içerir.

2. **record_system_audio.py** - Sistem seslerini ve mikrofonu kaydeden bağımsız modül.

3. **config_audio.py** - Ses kayıt sistemi için yapılandırma ayarları.

## Yapılandırma

Sistemin davranışını özelleştirmek için `config_audio.py` dosyasını düzenleyebilirsiniz. Bu dosya, kayıt süresi, ses kalitesi, Discord webhook URL'leri gibi ses kaydı ile ilgili tüm ayarları içerir.

### Önemli Ayarlar

- `DEFAULT_RECORDING_DURATION`: Saniye cinsinden her ses kaydının süresi
- `SEND_MIXED_AUDIO`: Mikrofon ve sistem sesinin karışımını gönderme seçeneği
- `SEND_MIC_AUDIO`: Sadece mikrofon sesini gönderme seçeneği
- `SEND_SYSTEM_AUDIO`: Sadece sistem sesini gönderme seçeneği
- `AUDIO_WEBHOOK_URL`: Discord webhook URL'si

## Kurulum ve Çalıştırma

1. Gerekli paketleri yükleyin:
   ```
   pip install pyautogui pynput mss numpy Pillow psutil screeninfo requests soundcard soundfile pyaudio pydub
   ```

2. `monitor.py` dosyasını çalıştırın:
   ```
   python monitor.py
   ```

3. Test modunda ses kaydı yapmak için:
   ```
   python record_system_audio.py --test
   ```

## Sorun Giderme

Ses kaydı çalışmazsa:

1. `audio_record_log.txt` ve `audio_crash_log.txt` dosyalarını kontrol edin
2. FFmpeg kurulu olduğundan emin olun veya `FFMPEG_AUTO_DOWNLOAD` ayarını `True` olarak ayarlayın
3. Sistem ses ayarlarında "Stereo Mix" veya benzer bir sistem ses kaynağı etkinleştirin

## Ek Bilgiler

- Sistem, normal koşullarda otomatik olarak yeniden başlatılır
- Ses kaydı ve ekran görüntüleri birbirinden bağımsız çalışır
- Tüm log dosyaları proje klasöründe saklanır
