import asyncio
import os
import logging
import mimetypes
import shutil
import base64
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from motor.motor_asyncio import AsyncIOMotorClient
from config import *
import aiofiles
import ffmpeg
from cryptography.fernet import Fernet
import hashlib
from datetime import datetime
from typing import Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot
app = Client("video_merge_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# MongoDB client
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client[DATABASE_NAME]

# Encryption for sessions
cipher = Fernet(base64.urlsafe_b64decode(ENCRYPTION_KEY))

# Ensure temp directory exists
os.makedirs(TEMP_DIR, exist_ok=True)

# User states
user_states = {}
active_tasks = {}

maintenance_mode = False

# Database Models
class User:
    def __init__(self, user_id: int, username: Optional[str] = None, premium: bool = False, session_hash: Optional[str] = None):
        self.user_id = user_id
        self.username = username
        self.premium = premium
        self.session_hash = session_hash

    @classmethod
    async def get(cls, user_id: int):
        data = await db.users.find_one({"user_id": user_id})
        if data:
            return cls(**data)
        return None

    async def save(self):
        await db.users.update_one(
            {"user_id": self.user_id},
            {"$set": {
                "username": self.username,
                "premium": self.premium,
                "session_hash": self.session_hash
            }},
            upsert=True
        )

class FileRecord:
    def __init__(self, user_id: int, file_id: str, file_type: str, file_size: int, timestamp: datetime):
        self.user_id = user_id
        self.file_id = file_id
        self.file_type = file_type
        self.file_size = file_size
        self.timestamp = timestamp

    async def save(self):
        await db.files.insert_one({
            "user_id": self.user_id,
            "file_id": self.file_id,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "timestamp": self.timestamp
        })

# Function to get user tier
async def get_user_tier(user_id):
    user = await User.get(user_id)
    if user and user.premium:
        return "premium"
    return "normal"

# Function to validate file
def validate_file(file_name, file_size, formats, limit, mime_type=None):
    ext = file_name.split('.')[-1].lower()
    if ext not in formats:
        return False, f"Unsupported format: {ext}"
    if file_size > limit:
        return False, f"File too large: {file_size / (1024**3):.2f}GB > {limit / (1024**3):.2f}GB"
    if mime_type:
        guessed_mime = mimetypes.guess_type(file_name)[0]
        if guessed_mime != mime_type:
            return False, f"MIME type mismatch: expected {mime_type}, got {guessed_mime}"
    return True, None

# Handler for video upload
@app.on_message(filters.video)
async def handle_video(client, message: Message):
    user_id = message.from_user.id
    tier = await get_user_tier(user_id)
    limit = PREMIUM_VIDEO_LIMIT if tier == "premium" else NORMAL_VIDEO_LIMIT

    file_name = os.path.basename(message.video.file_name).replace('/', '_').replace('\\', '_')
    valid, error = validate_file(file_name, message.video.file_size, VIDEO_FORMATS, limit, message.video.mime_type)
    if not valid:
        await message.reply_text(error)
        return

    # Save metadata
    file_record = FileRecord(user_id, message.video.file_id, "video", message.video.file_size, datetime.utcnow())
    await file_record.save()

    user_states[user_id] = {"video": message.video.file_id, "video_size": message.video.file_size}
    await message.reply_text("Video received. Now send the audio file.")

# Handler for audio upload
@app.on_message(filters.audio)
async def handle_audio(client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_states or "video" not in user_states[user_id]:
        await message.reply_text("Please send a video first.")
        return

    tier = await get_user_tier(user_id)
    limit = PREMIUM_AUDIO_LIMIT if tier == "premium" else NORMAL_AUDIO_LIMIT

    file_name = os.path.basename(message.audio.file_name).replace('/', '_').replace('\\', '_')
    valid, error = validate_file(file_name, message.audio.file_size, AUDIO_FORMATS, limit, message.audio.mime_type)
    if not valid:
        await message.reply_text(error)
        return

    # Save metadata
    file_record = FileRecord(user_id, message.audio.file_id, "audio", message.audio.file_size, datetime.utcnow())
    await file_record.save()

    user_states[user_id]["audio"] = message.audio.file_id
    user_states[user_id]["audio_size"] = message.audio.file_size

    # Show inline buttons
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Replace Video Audio", callback_data="replace")],
        [InlineKeyboardButton("➕ Add Audio (Keep Original)", callback_data="add")]
    ])
    await message.reply_text("Choose merge mode:", reply_markup=keyboard)

# Callback handler for buttons
@app.on_callback_query()
async def handle_callback(client, callback_query):
    user_id = callback_query.from_user.id
    mode = callback_query.data

    if user_id in active_tasks:
        await callback_query.answer("Already processing a request.")
        return

    if user_id not in user_states or "audio" not in user_states[user_id]:
        await callback_query.answer("Invalid state.")
        return

    user_states[user_id]["mode"] = mode
    await callback_query.message.edit_text("Starting merge process...")

    # Start processing
    active_tasks[user_id] = True
    asyncio.create_task(process_merge(user_id, callback_query.message))

# Progress callback
async def progress_callback(current, total, message, stage):
    percent = int((current / total) * 100)
    await message.edit_text(f"{stage} {percent}%")

# Merge process
async def process_merge(user_id, message):
    if maintenance_mode:
        await message.edit_text("Bot is under maintenance. Try again later.")
        return

    # Check disk space (need at least 2GB free)
    stat = shutil.disk_usage(TEMP_DIR)
    if stat.free < 2 * 1024 * 1024 * 1024:
        await message.edit_text("Insufficient disk space.")
        return

    state = user_states[user_id]
    video_id = state["video"]
    audio_id = state["audio"]
    mode = state["mode"]

    # Download files
    await message.edit_text("⏬ Downloading video...")
    video_path = os.path.join(TEMP_DIR, f"{user_id}_video.mp4")
    await app.download_media(video_id, file_name=video_path, progress=progress_callback, progress_args=(message, "⏬ Downloading video:"))

    await message.edit_text("⏬ Downloading audio...")
    audio_path = os.path.join(TEMP_DIR, f"{user_id}_audio.mp3")
    await app.download_media(audio_id, file_name=audio_path, progress=progress_callback, progress_args=(message, "⏬ Downloading audio:"))

    await message.edit_text("🎛 Merging media...")
    output_path = os.path.join(TEMP_DIR, f"{user_id}_output.mp4")

    try:
        if mode == "replace":
            # Replace audio: copy video, replace audio
            (
                ffmpeg
                .input(video_path)
                .input(audio_path)
                .output(output_path, vcodec='copy', acodec='aac', map=['0:v', '1:a'])
                .run(overwrite_output=True)
            )
        else:
            # Add audio (mix): mix original and new audio with volume balancing
            video = ffmpeg.input(video_path)
            audio_orig = ffmpeg.input(video_path).audio
            audio_new = ffmpeg.input(audio_path)
            # Normalize volumes
            audio_orig_norm = audio_orig.filter('volume', '0.5')
            audio_new_norm = audio_new.filter('volume', '0.5')
            mixed = ffmpeg.filter([audio_orig_norm, audio_new_norm], 'amix', inputs=2, duration='longest')
            (
                ffmpeg
                .output(video.video, mixed, output_path, vcodec='copy', acodec='aac')
                .run(overwrite_output=True)
            )
    except ffmpeg.Error as e:
        await message.edit_text(f"Merging failed: {e.stderr.decode()}")
        return

    await message.edit_text("⏫ Uploading final video...")
    try:
        with open(output_path, 'rb') as f:
            sent = await app.send_video(user_id, f, caption=f"Merged successfully! Mode: {mode}", progress=progress_callback, progress_args=(message, "⏫ Uploading final video:"))
        final_size = os.path.getsize(output_path)
        tier = await get_user_tier(user_id)
        log_msg = f"User: {user_id}\nTier: {tier}\nVideo size: {state.get('video_size', 'N/A')}\nAudio size: {state.get('audio_size', 'N/A')}\nMode: {mode}\nFinal size: {final_size}\nStatus: Success"
        await app.send_message(LOG_CHANNEL_ID, log_msg)
    except Exception as e:
        log_msg = f"User: {user_id}\nMode: {mode}\nStatus: Failed - {str(e)}"
        await app.send_message(LOG_CHANNEL_ID, log_msg)
        await message.edit_text("Upload failed.")
        del active_tasks[user_id]
        return

    # Cleanup
    os.remove(video_path)
    os.remove(audio_path)
    os.remove(output_path)
    del user_states[user_id]
    del active_tasks[user_id]

# Premium command
@app.on_message(filters.command("premium"))
async def premium(client, message):
    user_id = message.from_user.id
    if len(message.command) < 2:
        await message.reply_text("Please provide your Telegram String Session after /premium")
        return

    session_string = message.command[1]
    try:
        # Validate session
        temp_client = Client("temp", api_id=API_ID, api_hash=API_HASH, session_string=session_string)
        await temp_client.start()
        me = await temp_client.get_me()
        await temp_client.stop()

        # Encrypt session
        encrypted_session = cipher.encrypt(session_string.encode()).decode()

        # Save user
        user = await User.get(user_id)
        if not user:
            user = User(user_id, message.from_user.username)
        user.premium = True
        user.session_hash = encrypted_session
        await user.save()

        await message.reply_text("Premium activated successfully!")
    except Exception as e:
        await message.reply_text(f"Invalid session: {str(e)}")

# Admin commands
@app.on_message(filters.command("stats") & filters.user(ADMIN_IDS))
async def stats(client, message):
    total_users = await db.users.count_documents({})
    premium_users = await db.users.count_documents({"premium": True})
    total_files = await db.files.count_documents({})
    await message.reply_text(f"Total users: {total_users}\nPremium users: {premium_users}\nTotal files: {total_files}")

@app.on_message(filters.command("clean") & filters.user(ADMIN_IDS))
async def clean(client, message):
    # Clean old files (e.g., older than 1 day)
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=1)
    deleted = await db.files.delete_many({"timestamp": {"$lt": cutoff}})
    await message.reply_text(f"Cleaned {deleted.deleted_count} old records.")

@app.on_message(filters.command("premium") & filters.user(ADMIN_IDS))
async def admin_premium(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /premium <user_id>")
        return
    try:
        target_id = int(message.command[1])
        user = await User.get(target_id)
        if not user:
            user = User(target_id)
        user.premium = True
        await user.save()
        await message.reply_text(f"Premium set for user {target_id}")
    except ValueError:
        await message.reply_text("Invalid user ID")

@app.on_message(filters.command("broadcast") & filters.user(ADMIN_IDS))
async def broadcast(client, message):
    if not message.reply_to_message:
        await message.reply_text("Reply to a message to broadcast.")
        return
    users = db.users.find({})
    count = 0
    async for user in users:
        try:
            await app.send_message(user["user_id"], message.reply_to_message.text or message.reply_to_message.caption)
            count += 1
        except:
            pass
    await message.reply_text(f"Broadcasted to {count} users.")

@app.on_message(filters.command("maintenance") & filters.user(ADMIN_IDS))
async def maintenance(client, message):
    global maintenance_mode
    maintenance_mode = not maintenance_mode
    await message.reply_text(f"Maintenance mode: {'ON' if maintenance_mode else 'OFF'}")

if __name__ == "__main__":
    app.run()