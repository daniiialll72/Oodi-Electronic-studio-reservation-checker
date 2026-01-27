# Docker Setup Guide

## Quick Start

### 1. Create `.env` file

The `.env` file is already created in the project. Edit it with your settings:

```bash
nano .env
# or use any text editor
```

### 2. Fill in your notification settings

**For Telegram:**
```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

**For Email (Gmail example):**
```env
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password_here
EMAIL_TO=recipient@example.com
```

**Monitoring settings:**
```env
MONITOR_INTERVAL=5
# MONITOR_DATE=2026-01-24  # Optional: leave empty for today
```

### 3. Start the container

```bash
docker-compose up -d
```

The `.env` file is automatically loaded by docker-compose (see `env_file: - .env` in docker-compose.yml).

### 4. View logs

```bash
docker-compose logs -f
```

### 5. Stop the container

```bash
docker-compose down
```

## How Environment Variables are Passed

### With Docker Compose (Recommended)

The `docker-compose.yml` file has:
```yaml
env_file:
  - .env
```

This automatically loads all variables from `.env` into the container.

### With Docker Directly

**Option 1: Use --env-file**
```bash
docker run -d \
  --name oodi-monitor \
  --restart unless-stopped \
  --env-file .env \
  oodi-monitor
```

**Option 2: Pass variables directly**
```bash
docker run -d \
  --name oodi-monitor \
  --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN="your_token" \
  -e TELEGRAM_CHAT_ID="your_chat_id" \
  -e MONITOR_INTERVAL=5 \
  oodi-monitor
```

## Sample .env File

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789

# Email Configuration (Gmail example)
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_TO=recipient@example.com

# Monitoring Settings
MONITOR_INTERVAL=5
# MONITOR_DATE=2026-01-24
```

## Notes

- Leave variables empty if you don't want to use that notification method
- The `.env` file is automatically ignored by git (in .gitignore)
- You can have both Telegram and Email configured - it will send to both
- Empty variables are ignored by the entrypoint script

