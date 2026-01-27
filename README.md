# Oodi Electronic Studio Reservation Checker

A Python script to check available reservation slots for electronic studios at Oodi library in Helsinki, Finland. Uses GraphQL API to fetch real-time reservation data from Varaamo.

## Features

- ✅ Real-time availability checking via GraphQL API
- ✅ Day-specific working hours (Monday: 4pm-8pm, Tue-Fri: 8am-8:30pm, Sat-Sun: 10am-7:30pm)
- ✅ Reservation constraints (min 1h, max 4h)
- ✅ Filters out past time slots automatically
- ✅ Monitoring mode with notifications (Telegram, Email, or System)
- ✅ Check any date with `--date` parameter

## Installation

```bash
pip install requests
```

## Usage

### Basic Usage

Check today's availability:
```bash
python3 check_oodi_slots.py
```

Check a specific date:
```bash
python3 check_oodi_slots.py --date 2026-01-24
```

### Monitoring Mode with Notifications

The script can continuously monitor for available slots and send notifications when they become available.

#### Telegram Notifications

1. Create a Telegram bot:
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Send `/newbot` and follow instructions
   - Save the bot token

2. Get your chat ID:
   - Message your bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your chat ID in the response

3. Run with Telegram notifications:
```bash
python3 check_oodi_slots.py --monitor --telegram-token YOUR_BOT_TOKEN --telegram-chat-id YOUR_CHAT_ID
```

Or use environment variables:
```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
python3 check_oodi_slots.py --monitor
```

#### Email Notifications

For Gmail:
```bash
python3 check_oodi_slots.py --monitor \
  --email-smtp-server smtp.gmail.com \
  --email-smtp-port 587 \
  --email-username your_email@gmail.com \
  --email-password your_app_password \
  --email-to recipient@example.com
```

Or use environment variables:
```bash
export EMAIL_SMTP_SERVER="smtp.gmail.com"
export EMAIL_SMTP_PORT="587"
export EMAIL_USERNAME="your_email@gmail.com"
export EMAIL_PASSWORD="your_app_password"
export EMAIL_TO="recipient@example.com"
python3 check_oodi_slots.py --monitor
```

**Note for Gmail:** You need to use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.

#### Custom Monitoring Interval

Check every 10 minutes instead of default 5:
```bash
python3 check_oodi_slots.py --monitor --interval 10
```

### All Options

```bash
python3 check_oodi_slots.py --help
```

## Configuration

### Environment Variables

You can set these environment variables instead of passing command-line arguments:

- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `TELEGRAM_CHAT_ID` - Telegram chat ID
- `EMAIL_SMTP_SERVER` - SMTP server address
- `EMAIL_SMTP_PORT` - SMTP port number
- `EMAIL_USERNAME` - Email username
- `EMAIL_PASSWORD` - Email password/app password
- `EMAIL_TO` - Recipient email address

### Example: Running in Background

On macOS/Linux, you can run the monitoring in the background:

```bash
nohup python3 check_oodi_slots.py --monitor --interval 5 > monitor.log 2>&1 &
```

Stop monitoring:
```bash
pkill -f "check_oodi_slots.py --monitor"
```

## Working Hours

- **Monday**: 16:00 - 20:00 (4pm - 8pm)
- **Tuesday - Friday**: 08:00 - 20:30 (8am - 8:30pm)
- **Saturday - Sunday**: 10:00 - 19:30 (10am - 7:30pm)

## Reservation Constraints

- Minimum duration: 1 hour
- Maximum duration: 4 hours
- Only shows slots that can accommodate these constraints

## Docker Deployment

Run the monitoring script in a Docker container for continuous operation.

### Quick Start with Docker Compose

1. **Create and configure `.env` file:**
```bash
# The .env file is already created with sample values
# Edit it with your notification settings:
nano .env
# or
vim .env
# or use any text editor
```

2. **Fill in your settings in `.env`:**
   - For **Telegram**: Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
   - For **Email**: Add all email settings (SMTP server, port, username, password, recipient)
   - Set `MONITOR_INTERVAL` (default: 5 minutes)

3. **Start the container:**
```bash
docker-compose up -d
```

The `.env` file is automatically loaded by docker-compose.

4. **View logs:**
```bash
docker-compose logs -f
```

5. **Stop the container:**
```bash
docker-compose down
```

### Docker Compose Options

The container will automatically restart unless stopped. You can configure:

- `MONITOR_INTERVAL`: Check interval in minutes (default: 5)
- `MONITOR_DATE`: Specific date to monitor (leave empty for today)
- All Telegram and Email environment variables

### Using Docker Directly (without docker-compose)

Build the image:
```bash
docker build -t oodi-monitor .
```

**Option 1: Use .env file**
```bash
docker run -d \
  --name oodi-monitor \
  --restart unless-stopped \
  --env-file .env \
  oodi-monitor
```

**Option 2: Pass environment variables directly**
```bash
docker run -d \
  --name oodi-monitor \
  --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN="your_token" \
  -e TELEGRAM_CHAT_ID="your_chat_id" \
  -e MONITOR_INTERVAL=5 \
  oodi-monitor
```

Or with email:
```bash
docker run -d \
  --name oodi-monitor \
  --restart unless-stopped \
  -e EMAIL_SMTP_SERVER="smtp.gmail.com" \
  -e EMAIL_SMTP_PORT="587" \
  -e EMAIL_USERNAME="your_email@gmail.com" \
  -e EMAIL_PASSWORD="your_app_password" \
  -e EMAIL_TO="recipient@example.com" \
  -e MONITOR_INTERVAL=5 \
  oodi-monitor
```

### View Logs

```bash
# Docker Compose
docker-compose logs -f

# Docker
docker logs -f oodi-monitor
```

### Stop Container

```bash
# Docker Compose
docker-compose down

# Docker
docker stop oodi-monitor
docker rm oodi-monitor
```

## License

MIT
