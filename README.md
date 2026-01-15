# 🚀 NASA APOD Wallpaper for macOS

Automatically set your macOS desktop wallpaper to NASA's stunning [Astronomy Picture of the Day](https://apod.nasa.gov/) every morning.

![macOS](https://img.shields.io/badge/macOS-Monterey%2B-blue)
![Python](https://img.shields.io/badge/Python-3.8%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ Features

- 🌌 **Daily Updates**: Automatically fetches NASA's APOD every morning
- 🖼️ **HD Quality**: Downloads the highest quality version available
- 📱 **Notifications**: macOS notifications with image title and description
- 🔄 **Smart Retries**: Exponential backoff for network errors
- 🗂️ **Auto-Cleanup**: Keeps only the last N wallpapers (configurable)
- 📝 **Detailed Logging**: All operations logged for troubleshooting
- 🎬 **Video Handling**: Uses thumbnails when APOD is a video
- 🔒 **Duplicate Prevention**: Won't re-download the same image twice

## 📋 Prerequisites

- **macOS**: Monterey (12.0) or later
- **Python**: 3.8 or later
- **Internet**: Active connection for API access

### Check Python Version

```bash
python3 --version
```

If Python 3 is not installed, you can install it via:
- [Official Python Website](https://www.python.org/downloads/)
- Homebrew: `brew install python3`

## 🔑 Getting a NASA API Key

While this application works with the `DEMO_KEY`, it has a rate limit of 30 requests per hour. For personal use, get a free API key:

1. Visit [https://api.nasa.gov/](https://api.nasa.gov/)
2. Fill out the simple signup form
3. Check your email for the API key
4. Add it to your `config.json` file

## 🚀 Installation

### Quick Start

```bash
# Clone or download the project
cd nasa-wallpaper

# Run the setup script
chmod +x setup.sh
./setup.sh
```

### With Custom API Key

```bash
./setup.sh --api-key YOUR_NASA_API_KEY
```

### What Setup Does

1. ✅ Checks for Python 3.8+
2. ✅ Installs required Python packages
3. ✅ Creates necessary directories
4. ✅ Sets up configuration file
5. ✅ Installs launchd agent for daily execution
6. ✅ Runs initial test to verify everything works

## ⚙️ Configuration

Edit `config.json` to customize behavior:

```json
{
    "api_key": "YOUR_NASA_API_KEY",
    "keep_last_n_wallpapers": 30,
    "show_notifications": true,
    "max_retries": 3,
    "retry_delay_base": 2,
    "timeout": 30,
    "hd_preferred": true
}
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `api_key` | `DEMO_KEY` | Your NASA API key |
| `keep_last_n_wallpapers` | `30` | Number of old wallpapers to keep |
| `show_notifications` | `true` | Show macOS notifications |
| `max_retries` | `3` | Number of retry attempts on failure |
| `retry_delay_base` | `2` | Base delay (seconds) for exponential backoff |
| `timeout` | `30` | Request timeout in seconds |
| `hd_preferred` | `true` | Download HD version when available |

## 📁 Project Structure

```
nasa-wallpaper/
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── config.json.example    # Example configuration
├── config.json           # Your configuration (created by setup)
├── setup.sh              # Installation script
├── uninstall.sh          # Removal script
├── nasa_wallpaper.py     # Main Python script
└── com.nasa.wallpaper.plist  # launchd configuration
```

## 📍 Important Paths

| What | Where |
|------|-------|
| Wallpapers | `~/Pictures/NASA_APOD/` |
| Log File | `~/Library/Logs/nasa_wallpaper.log` |
| LaunchAgent | `~/Library/LaunchAgents/com.nasa.wallpaper.plist` |
| Config | `./config.json` (in project directory) |

## 🔧 Manual Usage

### Run Manually

```bash
python3 nasa_wallpaper.py
```

### View Logs

```bash
# Follow logs in real-time
tail -f ~/Library/Logs/nasa_wallpaper.log

# View last 50 lines
tail -50 ~/Library/Logs/nasa_wallpaper.log
```

### Check LaunchAgent Status

```bash
# Check if agent is loaded
launchctl list | grep nasa

# View agent details
launchctl print gui/$(id -u)/com.nasa.wallpaper
```

### Reload LaunchAgent

```bash
# Unload and reload
launchctl unload ~/Library/LaunchAgents/com.nasa.wallpaper.plist
launchctl load ~/Library/LaunchAgents/com.nasa.wallpaper.plist
```

### Force Run Now

```bash
launchctl kickstart -k gui/$(id -u)/com.nasa.wallpaper
```

## 🛠️ Troubleshooting

### Wallpaper Not Changing

1. **Check logs for errors:**
   ```bash
   cat ~/Library/Logs/nasa_wallpaper.log
   ```

2. **Verify script runs manually:**
   ```bash
   python3 nasa_wallpaper.py
   ```

3. **Check System Preferences permissions:**
   - Go to **System Preferences → Security & Privacy → Privacy**
   - Ensure **Automation** and **Full Disk Access** have necessary permissions

### API Rate Limit Errors

- The `DEMO_KEY` is limited to 30 requests/hour
- Get a free personal key at [api.nasa.gov](https://api.nasa.gov/)
- Update `config.json` with your key

### Network Errors

The script includes automatic retry with exponential backoff. If you're behind a proxy:

1. Set environment variables:
   ```bash
   export HTTP_PROXY=http://proxy:port
   export HTTPS_PROXY=http://proxy:port
   ```

2. Or add to the plist file in `EnvironmentVariables`

### LaunchAgent Not Running

1. **Check if loaded:**
   ```bash
   launchctl list | grep nasa
   ```

2. **Check plist syntax:**
   ```bash
   plutil -lint ~/Library/LaunchAgents/com.nasa.wallpaper.plist
   ```

3. **Reload agent:**
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.nasa.wallpaper.plist
   launchctl load ~/Library/LaunchAgents/com.nasa.wallpaper.plist
   ```

### Permission Issues

If you see AppleScript errors:
1. Open **System Preferences → Security & Privacy → Privacy**
2. Select **Automation** in the sidebar
3. Allow Terminal (or your terminal app) to control System Events

### Video Instead of Image

When NASA features a video as APOD:
- The script attempts to use the video thumbnail
- If no thumbnail is available, it skips that day
- You'll receive a notification about the video

## 🗑️ Uninstalling

### Complete Removal

```bash
./uninstall.sh
```

### Keep Wallpapers

```bash
./uninstall.sh --keep-wallpapers
```

### Keep Configuration

```bash
./uninstall.sh --keep-config
```

## 🔄 Changing the Schedule

The default schedule is 8:00 AM daily. To change:

1. Edit the plist file:
   ```bash
   nano ~/Library/LaunchAgents/com.nasa.wallpaper.plist
   ```

2. Find and modify the `StartCalendarInterval` section:
   ```xml
   <key>StartCalendarInterval</key>
   <dict>
       <key>Hour</key>
       <integer>9</integer>  <!-- Change to desired hour (24h format) -->
       <key>Minute</key>
       <integer>30</integer> <!-- Change to desired minute -->
   </dict>
   ```

3. Reload the agent:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.nasa.wallpaper.plist
   launchctl load ~/Library/LaunchAgents/com.nasa.wallpaper.plist
   ```

### Run at Multiple Times

```xml
<key>StartCalendarInterval</key>
<array>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <dict>
        <key>Hour</key>
        <integer>12</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
</array>
```

## 📊 How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    Daily at 8:00 AM                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Check if already downloaded today (prevent duplicates)  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Fetch APOD metadata from NASA API                       │
│     - Handle rate limits and errors                         │
│     - Retry with exponential backoff                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Check media type (image vs video)                       │
│     - Use thumbnail for videos                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Download HD image to ~/Pictures/NASA_APOD/              │
│     - Validate image format                                 │
│     - Save with date-stamped filename                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  5. Set as desktop wallpaper via AppleScript                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  6. Send macOS notification                                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  7. Cleanup old wallpapers (keep last N)                    │
└─────────────────────────────────────────────────────────────┘
```

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [NASA APOD](https://apod.nasa.gov/) for the amazing daily images
- [NASA Open APIs](https://api.nasa.gov/) for providing free API access

---

**Enjoy your daily dose of cosmic wonder! 🌟**
