import os

# Telegram API credentials
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = "video_merge_bot"

# Log channel
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))

# Admin user IDs (comma-separated)
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS").split(",")]

# File size limits (in bytes)
NORMAL_VIDEO_LIMIT = 2 * 1024 * 1024 * 1024  # 2GB
NORMAL_AUDIO_LIMIT = 1 * 1024 * 1024 * 1024  # 1GB
PREMIUM_VIDEO_LIMIT = 4 * 1024 * 1024 * 1024  # 4GB
PREMIUM_AUDIO_LIMIT = 4 * 1024 * 1024 * 1024  # 4GB

# Supported formats
VIDEO_FORMATS = ['mp4', 'mkv', 'mov', 'avi']
AUDIO_FORMATS = ['mp3', 'aac', 'wav', 'm4a', 'ogg']

# Temp directory
TEMP_DIR = "temp"

# Encryption key for sessions (generate a secure key)
import base64
from cryptography.fernet import Fernet

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", base64.urlsafe_b64encode(b'0' * 32).decode())