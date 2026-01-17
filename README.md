# Video Merging Bot

A Telegram bot that allows users to merge videos with audio files. Users can replace the original audio or add new audio to existing videos.

## Features

- **Video and Audio Merging**: Upload a video and an audio file, then choose to replace the video's audio or mix it with the original.
- **File Validation**: Supports specific formats and size limits based on user tier.
- **User Tiers**: Normal and premium users with different file size limits.
- **Premium Activation**: Users can activate premium by providing a Telegram session string.
- **Admin Commands**: Admins can view stats, clean old records, set premium for users, broadcast messages, and toggle maintenance mode.
- **Logging**: All activities are logged to a specified channel.
- **MongoDB Integration**: Stores user data and file records.

## Supported Formats

- **Videos**: mp4, mkv, mov, avi
- **Audio**: mp3, aac, wav, m4a, ogg

## File Size Limits

- **Normal Users**:
  - Video: 2GB
  - Audio: 1GB
- **Premium Users**:
  - Video: 4GB
  - Audio: 4GB

## Bot Commands

### User Commands

- `/premium <session_string>`: Activate premium by providing your Telegram session string.

### Admin Commands (Only for users in ADMIN_IDS)

- `/stats`: Get total users, premium users, and total files.
- `/clean`: Clean old file records (older than 1 day).
- `/premium <user_id>`: Set premium for a specific user.
- `/broadcast`: Broadcast a message to all users (reply to a message).
- `/maintenance`: Toggle maintenance mode on/off.

## How to Deploy on Heroku

1. **Fork this repository** to your GitHub account.

2. **Create a Heroku app**:
   - Go to [Heroku Dashboard](https://dashboard.heroku.com/).
   - Click "New" > "Create new app".
   - Give it a name and choose your region.

3. **Connect to GitHub**:
   - In your Heroku app dashboard, go to "Deploy" tab.
   - Connect your GitHub account and select the forked repository.

4. **Set Environment Variables**:
   - Go to "Settings" tab > "Config Vars".
   - Add the following variables:
     - `API_ID`: Your Telegram API ID
     - `API_HASH`: Your Telegram API Hash
     - `BOT_TOKEN`: Your bot token from @BotFather
     - `MONGO_URI`: MongoDB connection string
     - `LOG_CHANNEL_ID`: Channel ID for logging
     - `ADMIN_IDS`: Comma-separated list of admin user IDs

5. **Deploy**:
   - In "Deploy" tab, enable automatic deploys or manually deploy from the main branch.
   - Heroku will build the app using the specified buildpacks (Python and FFmpeg).

6. **Start the Worker**:
   - The app is configured to run as a worker process.
   - Once deployed, the bot should start automatically.

## Requirements

- Python 3.8+
- MongoDB
- FFmpeg (handled by buildpack)

## Local Development

1. Clone the repository.
2. Install dependencies: `pip install -r requirements.txt`
3. Set environment variables or update `config.py`.
4. Run: `python main.py`

## License

This project is open-source. Feel free to modify and distribute.