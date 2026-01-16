#!/usr/bin/env python3
"""
NASA Astronomy Picture of the Day (APOD) Wallpaper Setter

This script fetches NASA's daily APOD image and sets it as the macOS desktop wallpaper.
It includes error handling, retry logic, logging, duplicate prevention, and text overlay.

Author: NASA Wallpaper App
License: MIT
"""

import json
import logging
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image, ImageDraw, ImageFont

# Constants
CONFIG_PATH = Path(__file__).parent / "config.json"
DEFAULT_CONFIG = {
    "api_key": "DEMO_KEY",
    "keep_last_n_wallpapers": 30,
    "show_notifications": True,
    "max_retries": 3,
    "retry_delay_base": 2,
    "timeout": 30,
    "hd_preferred": True,
    "show_description_overlay": True,
    "overlay_max_chars": 300,
    "overlay_opacity": 0.7,
    "overlay_font_size_title": 28,
    "overlay_font_size_description": 18
}

# Directories
PICTURES_DIR = Path.home() / "Pictures" / "NASA_APOD"
LOG_DIR = Path.home() / "Library" / "Logs"
LOG_FILE = LOG_DIR / "nasa_wallpaper.log"
CACHE_FILE = PICTURES_DIR / ".last_download.json"


def setup_logging() -> logging.Logger:
    """
    Set up logging configuration with both file and console handlers.
    
    Returns:
        logging.Logger: Configured logger instance.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger("nasa_wallpaper")
    logger.setLevel(logging.DEBUG)
    
    if logger.handlers:
        return logger
    
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(funcName)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_format)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json file."""
    config = DEFAULT_CONFIG.copy()
    
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                config.update(user_config)
        except (json.JSONDecodeError, IOError) as e:
            logging.getLogger("nasa_wallpaper").warning(
                f"Could not load config file: {e}. Using defaults."
            )
    
    return config


def create_session_with_retry(config: Dict[str, Any]) -> requests.Session:
    """Create a requests session with retry logic and exponential backoff."""
    session = requests.Session()
    
    retry_strategy = Retry(
        total=config["max_retries"],
        backoff_factor=config["retry_delay_base"],
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def fetch_apod_data(
    session: requests.Session,
    api_key: str,
    timeout: int,
    logger: logging.Logger
) -> Optional[Dict[str, Any]]:
    """Fetch APOD metadata from NASA API."""
    api_url = "https://api.nasa.gov/planetary/apod"
    params = {"api_key": api_key}
    
    logger.info("Fetching APOD data from NASA API...")
    
    try:
        response = session.get(api_url, params=params, timeout=timeout)
        
        if response.status_code == 429:
            logger.error("API rate limit exceeded. Please try again later.")
            return None
        
        if response.status_code != 200:
            logger.error(f"API request failed with status {response.status_code}: {response.text}")
            return None
        
        data = response.json()
        logger.info(f"Successfully fetched APOD: {data.get('title', 'Unknown')}")
        logger.debug(f"APOD date: {data.get('date')}")
        logger.debug(f"Media type: {data.get('media_type')}")
        
        return data
        
    except requests.exceptions.Timeout:
        logger.error("Request timed out while fetching APOD data.")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("Network connection error. Check your internet connection.")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        return None
    except json.JSONDecodeError:
        logger.error("Invalid JSON response from API.")
        return None


def is_already_downloaded(date: str, logger: logging.Logger) -> bool:
    """Check if today's APOD has already been downloaded."""
    if not CACHE_FILE.exists():
        return False
    
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
            last_date = cache.get("date")
            if last_date == date:
                logger.info(f"APOD for {date} already downloaded. Skipping.")
                return True
    except (json.JSONDecodeError, IOError):
        pass
    
    return False


def save_download_cache(date: str, filename: str, title: str) -> None:
    """Save download information to cache file."""
    cache = {
        "date": date,
        "filename": filename,
        "title": title,
        "downloaded_at": datetime.now().isoformat()
    }
    
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def get_image_url(apod_data: Dict[str, Any], hd_preferred: bool) -> Optional[str]:
    """Extract image URL from APOD data, handling video content."""
    media_type = apod_data.get("media_type", "image")
    
    if media_type == "video":
        thumbnail_url = apod_data.get("thumbnail_url")
        if thumbnail_url:
            return thumbnail_url
        return None
    
    if media_type == "image":
        if hd_preferred and "hdurl" in apod_data:
            return apod_data["hdurl"]
        return apod_data.get("url")
    
    return None


def validate_image_format(url: str, logger: logging.Logger) -> bool:
    """Validate that the URL points to a supported image format."""
    valid_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tiff", ".bmp"}
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    for ext in valid_extensions:
        if path.endswith(ext):
            return True
    
    if "image" in url.lower():
        logger.warning(f"URL may be an image but has unknown extension: {url}")
        return True
    
    logger.warning(f"Unsupported image format: {url}")
    return False


def download_image(
    session: requests.Session,
    url: str,
    date: str,
    timeout: int,
    logger: logging.Logger
) -> Optional[Path]:
    """Download image from URL and save to Pictures directory."""
    PICTURES_DIR.mkdir(parents=True, exist_ok=True)
    
    parsed = urlparse(url)
    path_ext = Path(parsed.path).suffix.lower()
    if not path_ext or path_ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        path_ext = ".jpg"
    
    filename = f"NASA_APOD_{date}_original{path_ext}"
    filepath = PICTURES_DIR / filename
    
    logger.info(f"Downloading image to {filepath}...")
    
    try:
        response = session.get(url, timeout=timeout, stream=True)
        
        if response.status_code != 200:
            logger.error(f"Failed to download image: HTTP {response.status_code}")
            return None
        
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            logger.error(f"Invalid content type: {content_type}")
            return None
        
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        if filepath.stat().st_size == 0:
            logger.error("Downloaded file is empty")
            filepath.unlink()
            return None
        
        logger.info(f"Successfully downloaded: {filename} ({filepath.stat().st_size / 1024 / 1024:.2f} MB)")
        return filepath
        
    except requests.exceptions.Timeout:
        logger.error("Download timed out")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Download error: {e}")
        return None
    except IOError as e:
        logger.error(f"File write error: {e}")
        return None


def get_system_font() -> Optional[str]:
    """Get a suitable system font path for macOS."""
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Geneva.ttf",
    ]
    
    for font_path in font_paths:
        if Path(font_path).exists():
            return font_path
    
    return None


def add_text_overlay(
    image_path: Path,
    title: str,
    description: str,
    date: str,
    config: Dict[str, Any],
    logger: logging.Logger
) -> Path:
    """Add title and description overlay to the top-left corner of the image."""
    if not config.get("show_description_overlay", True):
        logger.debug("Description overlay disabled in config")
        return image_path
    
    try:
        logger.info("Adding description overlay to image...")
        
        img = Image.open(image_path)
        img = img.convert("RGBA")
        
        width, height = img.size
        
        max_chars = config.get("overlay_max_chars", 500)  # More chars for 10+ lines
        opacity = config.get("overlay_opacity", 0.7)
        title_font_size = config.get("overlay_font_size_title", 20)  # Smaller
        desc_font_size = config.get("overlay_font_size_description", 14)  # Smaller
        
        # Scale font sizes based on image resolution
        scale_factor = min(width, height) / 1080
        title_font_size = max(int(title_font_size * scale_factor), 16)
        desc_font_size = max(int(desc_font_size * scale_factor), 11)
        
        # Load fonts
        font_path = get_system_font()
        try:
            if font_path:
                title_font = ImageFont.truetype(font_path, title_font_size)
                desc_font = ImageFont.truetype(font_path, desc_font_size)
            else:
                title_font = ImageFont.load_default()
                desc_font = ImageFont.load_default()
        except Exception as e:
            logger.warning(f"Could not load font: {e}. Using default.")
            title_font = ImageFont.load_default()
            desc_font = ImageFont.load_default()
        
        # Truncate description
        if len(description) > max_chars:
            description = description[:max_chars - 3] + "..."
        
        # Wrap text - narrower width for more lines
        padding = int(20 * scale_factor)
        max_text_width = int(width * 0.35)  # 35% of image width
        avg_char_width = desc_font_size * 0.55
        chars_per_line = int(max_text_width / avg_char_width)
        
        title_wrapped = textwrap.fill(title, width=chars_per_line)
        desc_wrapped = textwrap.fill(description, width=chars_per_line)
        date_text = f"📅 {date}"
        
        # Measure text
        temp_draw = ImageDraw.Draw(img)
        title_bbox = temp_draw.multiline_textbbox((0, 0), title_wrapped, font=title_font)
        desc_bbox = temp_draw.multiline_textbbox((0, 0), desc_wrapped, font=desc_font)
        date_bbox = temp_draw.textbbox((0, 0), date_text, font=desc_font)
        
        title_height = title_bbox[3] - title_bbox[1]
        desc_height = desc_bbox[3] - desc_bbox[1]
        date_height = date_bbox[3] - date_bbox[1]
        
        text_width = max(
            title_bbox[2] - title_bbox[0],
            desc_bbox[2] - desc_bbox[0],
            date_bbox[2] - date_bbox[0]
        )
        
        # Calculate overlay box
        line_spacing = int(8 * scale_factor)
        box_width = text_width + (padding * 2)
        box_height = title_height + desc_height + date_height + (padding * 2) + (line_spacing * 3)
        
        # TOP-LEFT positioning with margin for menu bar
        margin = int(30 * scale_factor)
        menu_bar_offset = int(35 * scale_factor)  # Space for macOS menu bar
        box_x = margin
        box_y = margin + menu_bar_offset  # Top-left, below menu bar
        
        # Create overlay
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        
        alpha = int(255 * opacity)
        corner_radius = int(12 * scale_factor)
        
        overlay_draw.rounded_rectangle(
            [box_x, box_y, box_x + box_width, box_y + box_height],
            radius=corner_radius,
            fill=(0, 0, 0, alpha)
        )
        
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)
        
        # Draw text
        text_x = box_x + padding
        text_y = box_y + padding
        
        draw.text((text_x, text_y), date_text, font=desc_font, fill=(180, 180, 180, 255))
        text_y += date_height + line_spacing
        
        draw.multiline_text((text_x, text_y), title_wrapped, font=title_font, fill=(255, 255, 255, 255))
        text_y += title_height + line_spacing
        
        draw.multiline_text((text_x, text_y), desc_wrapped, font=desc_font, fill=(220, 220, 220, 255))
        
        # Save
        output_filename = f"NASA_APOD_{date}.png"
        output_path = PICTURES_DIR / output_filename
        
        img_rgb = img.convert("RGB")
        img_rgb.save(output_path, "PNG", quality=95)
        
        logger.info(f"Created overlay image: {output_filename}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to add text overlay: {e}")
        logger.info("Falling back to original image without overlay")
        return image_path


def set_wallpaper(image_path: Path, logger: logging.Logger) -> bool:
    """Set macOS desktop wallpaper using multiple methods for compatibility."""
    if not image_path.exists():
        logger.error(f"Image file not found: {image_path}")
        return False
    
    image_path_str = str(image_path.resolve())
    logger.info("Setting desktop wallpaper...")
    
    # Method 1: Try using AppKit (PyObjC) - works best on macOS Sequoia
    try:
        from AppKit import NSWorkspace, NSScreen
        from Foundation import NSURL
        
        file_url = NSURL.fileURLWithPath_(image_path_str)
        ws = NSWorkspace.sharedWorkspace()
        
        for screen in NSScreen.screens():
            ws.setDesktopImageURL_forScreen_options_error_(file_url, screen, {}, None)
        
        logger.info("Successfully set desktop wallpaper (AppKit method)")
        return True
    except ImportError:
        logger.debug("AppKit not available, trying AppleScript methods")
    except Exception as e:
        logger.debug(f"AppKit method failed: {e}")
    
    # Method 2: Try Finder AppleScript
    try:
        applescript = f'tell application "Finder" to set desktop picture to POSIX file "{image_path_str}"'
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            # Restart Dock to apply changes
            subprocess.run(["killall", "Dock"], capture_output=True, timeout=10)
            logger.info("Successfully set desktop wallpaper (Finder method)")
            return True
    except Exception as e:
        logger.debug(f"Finder method failed: {e}")
    
    # Method 3: Try System Events AppleScript
    try:
        applescript = f'''
        tell application "System Events"
            tell every desktop
                set picture to "{image_path_str}"
            end tell
        end tell
        '''
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            logger.info("Successfully set desktop wallpaper (System Events method)")
            return True
    except Exception as e:
        logger.debug(f"System Events method failed: {e}")
    
    # Method 4: Try using sqlite to modify desktop picture database
    try:
        import sqlite3
        db_path = Path.home() / "Library/Application Support/Dock/desktoppicture.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("UPDATE data SET value = ?", (image_path_str,))
            conn.commit()
            conn.close()
            subprocess.run(["killall", "Dock"], capture_output=True, timeout=10)
            logger.info("Successfully set desktop wallpaper (sqlite method)")
            return True
    except Exception as e:
        logger.debug(f"sqlite method failed: {e}")
    
    logger.error("All wallpaper setting methods failed")
    return False


def send_notification(
    title: str,
    description: str,
    show_notifications: bool,
    logger: logging.Logger
) -> None:
    """Send macOS notification with APOD information."""
    if not show_notifications:
        logger.debug("Notifications disabled, skipping")
        return
    
    max_desc_length = 200
    if len(description) > max_desc_length:
        description = description[:max_desc_length - 3] + "..."
    
    title = title.replace('"', '\\"').replace("'", "'")
    description = description.replace('"', '\\"').replace("'", "'")
    
    applescript = f'''
    display notification "{description}" with title "NASA APOD" subtitle "{title}"
    '''
    
    try:
        subprocess.run(["osascript", "-e", applescript], capture_output=True, timeout=10)
        logger.debug("Notification sent successfully")
    except subprocess.SubprocessError as e:
        logger.warning(f"Could not send notification: {e}")


def cleanup_old_wallpapers(keep_count: int, logger: logging.Logger) -> None:
    """Remove old wallpapers, keeping only the most recent N files."""
    if keep_count <= 0:
        logger.debug("Cleanup disabled (keep_count <= 0)")
        return
    
    try:
        images = sorted(
            [f for f in PICTURES_DIR.glob("NASA_APOD_*") if f.is_file() and not f.name.startswith(".")],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        dates_seen = set()
        files_to_remove = []
        
        for filepath in images:
            name = filepath.stem
            parts = name.replace("NASA_APOD_", "").split("_")
            date_part = parts[0] if parts else ""
            
            if date_part not in dates_seen:
                if len(dates_seen) < keep_count:
                    dates_seen.add(date_part)
                else:
                    files_to_remove.append(filepath)
            elif len(dates_seen) > keep_count:
                files_to_remove.append(filepath)
        
        for filepath in files_to_remove:
            try:
                filepath.unlink()
                logger.info(f"Cleaned up old wallpaper: {filepath.name}")
            except OSError as e:
                logger.warning(f"Could not remove {filepath.name}: {e}")
        
        if files_to_remove:
            logger.info(f"Cleaned up {len(files_to_remove)} old wallpaper(s)")
            
    except Exception as e:
        logger.warning(f"Cleanup error: {e}")


def main() -> int:
    """Main entry point for the NASA APOD wallpaper script."""
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("NASA APOD Wallpaper Script Started")
    logger.info(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    config = load_config()
    logger.debug(f"Configuration loaded: {json.dumps({k: v for k, v in config.items() if k != 'api_key'}, indent=2)}")
    
    session = create_session_with_retry(config)
    
    try:
        apod_data = fetch_apod_data(session, config["api_key"], config["timeout"], logger)
        
        if not apod_data:
            logger.error("Failed to fetch APOD data")
            return 1
        
        apod_date = apod_data.get("date", datetime.now().strftime("%Y-%m-%d"))
        
        if is_already_downloaded(apod_date, logger):
            existing_files = list(PICTURES_DIR.glob(f"NASA_APOD_{apod_date}.png"))
            if not existing_files:
                existing_files = list(PICTURES_DIR.glob(f"NASA_APOD_{apod_date}*"))
            if existing_files:
                set_wallpaper(existing_files[0], logger)
            return 0
        
        media_type = apod_data.get("media_type", "image")
        
        if media_type == "video":
            thumbnail_url = apod_data.get("thumbnail_url")
            if not thumbnail_url:
                logger.warning(f"Today's APOD is a video without thumbnail. Title: {apod_data.get('title', 'Unknown')}")
                send_notification(
                    apod_data.get("title", "NASA APOD"),
                    "Today's APOD is a video. Visit apod.nasa.gov to watch!",
                    config["show_notifications"],
                    logger
                )
                return 0
            logger.info("Today's APOD is a video. Using thumbnail image.")
        
        image_url = get_image_url(apod_data, config["hd_preferred"])
        
        if not image_url:
            logger.error("No valid image URL found in APOD data")
            return 1
        
        if not validate_image_format(image_url, logger):
            logger.error("Invalid or unsupported image format")
            return 1
        
        image_path = download_image(session, image_url, apod_date, config["timeout"], logger)
        
        if not image_path:
            logger.error("Failed to download image")
            return 1
        
        # Add text overlay
        final_image_path = add_text_overlay(
            image_path,
            apod_data.get("title", "NASA Astronomy Picture of the Day"),
            apod_data.get("explanation", ""),
            apod_date,
            config,
            logger
        )
        
        if not set_wallpaper(final_image_path, logger):
            logger.error("Failed to set wallpaper")
            return 1
        
        save_download_cache(apod_date, final_image_path.name, apod_data.get("title", "Unknown"))
        
        send_notification(
            apod_data.get("title", "NASA APOD"),
            apod_data.get("explanation", "New astronomy picture of the day!"),
            config["show_notifications"],
            logger
        )
        
        cleanup_old_wallpapers(config["keep_last_n_wallpapers"], logger)
        
        logger.info("NASA APOD Wallpaper Script completed successfully!")
        return 0
        
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
