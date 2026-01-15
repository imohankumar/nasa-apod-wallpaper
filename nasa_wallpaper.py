#!/usr/bin/env python3
"""
NASA Astronomy Picture of the Day (APOD) Wallpaper Setter

This script fetches NASA's daily APOD image and sets it as the macOS desktop wallpaper.
It includes error handling, retry logic, logging, and duplicate prevention.

Author: NASA Wallpaper App
License: MIT
"""

import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Constants
CONFIG_PATH = Path(__file__).parent / "config.json"
DEFAULT_CONFIG = {
    "api_key": "DEMO_KEY",
    "keep_last_n_wallpapers": 30,
    "show_notifications": True,
    "max_retries": 3,
    "retry_delay_base": 2,
    "timeout": 30,
    "hd_preferred": True
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
    # Ensure log directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger("nasa_wallpaper")
    logger.setLevel(logging.DEBUG)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # File handler with rotation-friendly format
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(funcName)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)
    
    # Console handler for interactive use
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_format)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.json file.
    
    Returns:
        Dict[str, Any]: Configuration dictionary with defaults applied.
    """
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
    """
    Create a requests session with retry logic and exponential backoff.
    
    Args:
        config: Configuration dictionary containing retry settings.
        
    Returns:
        requests.Session: Configured session with retry adapter.
    """
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
    """
    Fetch APOD metadata from NASA API.
    
    Args:
        session: Requests session with retry logic.
        api_key: NASA API key.
        timeout: Request timeout in seconds.
        logger: Logger instance.
        
    Returns:
        Optional[Dict[str, Any]]: APOD data dictionary or None on failure.
    """
    api_url = "https://api.nasa.gov/planetary/apod"
    params = {"api_key": api_key}
    
    logger.info("Fetching APOD data from NASA API...")
    
    try:
        response = session.get(api_url, params=params, timeout=timeout)
        
        # Handle rate limiting
        if response.status_code == 429:
            logger.error("API rate limit exceeded. Please try again later.")
            return None
        
        # Handle other errors
        if response.status_code != 200:
            logger.error(
                f"API request failed with status {response.status_code}: "
                f"{response.text}"
            )
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
    """
    Check if today's APOD has already been downloaded.
    
    Args:
        date: Date string in YYYY-MM-DD format.
        logger: Logger instance.
        
    Returns:
        bool: True if already downloaded, False otherwise.
    """
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
    """
    Save download information to cache file.
    
    Args:
        date: Date string in YYYY-MM-DD format.
        filename: Downloaded filename.
        title: APOD title.
    """
    cache = {
        "date": date,
        "filename": filename,
        "title": title,
        "downloaded_at": datetime.now().isoformat()
    }
    
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def get_image_url(apod_data: Dict[str, Any], hd_preferred: bool) -> Optional[str]:
    """
    Extract image URL from APOD data, handling video content.
    
    Args:
        apod_data: APOD API response data.
        hd_preferred: Whether to prefer HD version.
        
    Returns:
        Optional[str]: Image URL or None if not available.
    """
    media_type = apod_data.get("media_type", "image")
    
    if media_type == "video":
        # Try to get video thumbnail
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
    """
    Validate that the URL points to a supported image format.
    
    Args:
        url: Image URL to validate.
        logger: Logger instance.
        
    Returns:
        bool: True if format is valid, False otherwise.
    """
    valid_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tiff", ".bmp"}
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    for ext in valid_extensions:
        if path.endswith(ext):
            return True
    
    # Check if it might be a valid image without extension
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
    """
    Download image from URL and save to Pictures directory.
    
    Args:
        session: Requests session.
        url: Image URL.
        date: Date string for filename.
        timeout: Request timeout.
        logger: Logger instance.
        
    Returns:
        Optional[Path]: Path to downloaded image or None on failure.
    """
    # Ensure directory exists
    PICTURES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Determine file extension
    parsed = urlparse(url)
    path_ext = Path(parsed.path).suffix.lower()
    if not path_ext or path_ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        path_ext = ".jpg"
    
    filename = f"NASA_APOD_{date}{path_ext}"
    filepath = PICTURES_DIR / filename
    
    logger.info(f"Downloading image to {filepath}...")
    
    try:
        response = session.get(url, timeout=timeout, stream=True)
        
        if response.status_code != 200:
            logger.error(f"Failed to download image: HTTP {response.status_code}")
            return None
        
        # Verify content type
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            logger.error(f"Invalid content type: {content_type}")
            return None
        
        # Download with progress
        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0
        
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
        
        # Verify file was written
        if filepath.stat().st_size == 0:
            logger.error("Downloaded file is empty")
            filepath.unlink()
            return None
        
        logger.info(
            f"Successfully downloaded: {filename} "
            f"({filepath.stat().st_size / 1024 / 1024:.2f} MB)"
        )
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


def set_wallpaper(image_path: Path, logger: logging.Logger) -> bool:
    """
    Set macOS desktop wallpaper using AppleScript.
    
    Args:
        image_path: Path to the image file.
        logger: Logger instance.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    # Verify file exists and is readable
    if not image_path.exists():
        logger.error(f"Image file not found: {image_path}")
        return False
    
    applescript = f'''
    tell application "System Events"
        tell every desktop
            set picture to "{image_path}"
        end tell
    end tell
    '''
    
    logger.info("Setting desktop wallpaper...")
    
    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.error(f"AppleScript error: {result.stderr}")
            return False
        
        logger.info("Successfully set desktop wallpaper")
        return True
        
    except subprocess.TimeoutExpired:
        logger.error("Wallpaper setting timed out")
        return False
    except subprocess.SubprocessError as e:
        logger.error(f"Subprocess error: {e}")
        return False


def send_notification(
    title: str,
    description: str,
    show_notifications: bool,
    logger: logging.Logger
) -> None:
    """
    Send macOS notification with APOD information.
    
    Args:
        title: Notification title.
        description: Notification description (will be truncated).
        show_notifications: Whether notifications are enabled.
        logger: Logger instance.
    """
    if not show_notifications:
        logger.debug("Notifications disabled, skipping")
        return
    
    # Truncate description to reasonable length
    max_desc_length = 200
    if len(description) > max_desc_length:
        description = description[:max_desc_length - 3] + "..."
    
    # Escape special characters for AppleScript
    title = title.replace('"', '\\"').replace("'", "'")
    description = description.replace('"', '\\"').replace("'", "'")
    
    applescript = f'''
    display notification "{description}" with title "NASA APOD" subtitle "{title}"
    '''
    
    try:
        subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            timeout=10
        )
        logger.debug("Notification sent successfully")
    except subprocess.SubprocessError as e:
        logger.warning(f"Could not send notification: {e}")


def cleanup_old_wallpapers(keep_count: int, logger: logging.Logger) -> None:
    """
    Remove old wallpapers, keeping only the most recent N files.
    
    Args:
        keep_count: Number of wallpapers to keep.
        logger: Logger instance.
    """
    if keep_count <= 0:
        logger.debug("Cleanup disabled (keep_count <= 0)")
        return
    
    try:
        # Get all APOD images, sorted by modification time
        images = sorted(
            [f for f in PICTURES_DIR.glob("NASA_APOD_*") if f.is_file()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        # Remove files beyond keep count
        files_to_remove = images[keep_count:]
        
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
    """
    Main entry point for the NASA APOD wallpaper script.
    
    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    # Set up logging
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("NASA APOD Wallpaper Script Started")
    logger.info(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load configuration
    config = load_config()
    logger.debug(f"Configuration loaded: {json.dumps({k: v for k, v in config.items() if k != 'api_key'}, indent=2)}")
    
    # Create session with retry logic
    session = create_session_with_retry(config)
    
    try:
        # Fetch APOD data
        apod_data = fetch_apod_data(
            session,
            config["api_key"],
            config["timeout"],
            logger
        )
        
        if not apod_data:
            logger.error("Failed to fetch APOD data")
            return 1
        
        # Extract date and check for duplicates
        apod_date = apod_data.get("date", datetime.now().strftime("%Y-%m-%d"))
        
        if is_already_downloaded(apod_date, logger):
            # Still set wallpaper in case it was changed
            existing_files = list(PICTURES_DIR.glob(f"NASA_APOD_{apod_date}*"))
            if existing_files:
                set_wallpaper(existing_files[0], logger)
            return 0
        
        # Check media type and get image URL
        media_type = apod_data.get("media_type", "image")
        
        if media_type == "video":
            thumbnail_url = apod_data.get("thumbnail_url")
            if not thumbnail_url:
                logger.warning(
                    f"Today's APOD is a video without thumbnail. "
                    f"Title: {apod_data.get('title', 'Unknown')}"
                )
                send_notification(
                    apod_data.get("title", "NASA APOD"),
                    "Today's APOD is a video. Visit apod.nasa.gov to watch!",
                    config["show_notifications"],
                    logger
                )
                return 0
            logger.info("Today's APOD is a video. Using thumbnail image.")
        
        # Get image URL
        image_url = get_image_url(apod_data, config["hd_preferred"])
        
        if not image_url:
            logger.error("No valid image URL found in APOD data")
            return 1
        
        # Validate image format
        if not validate_image_format(image_url, logger):
            logger.error("Invalid or unsupported image format")
            return 1
        
        # Download image
        image_path = download_image(
            session,
            image_url,
            apod_date,
            config["timeout"],
            logger
        )
        
        if not image_path:
            logger.error("Failed to download image")
            return 1
        
        # Set wallpaper
        if not set_wallpaper(image_path, logger):
            logger.error("Failed to set wallpaper")
            return 1
        
        # Save cache
        save_download_cache(
            apod_date,
            image_path.name,
            apod_data.get("title", "Unknown")
        )
        
        # Send notification
        send_notification(
            apod_data.get("title", "NASA APOD"),
            apod_data.get("explanation", "New astronomy picture of the day!"),
            config["show_notifications"],
            logger
        )
        
        # Cleanup old wallpapers
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
