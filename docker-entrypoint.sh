#!/bin/sh
# Docker entrypoint script for Oodi reservation monitor

# Build command arguments
ARGS="--monitor --interval ${MONITOR_INTERVAL:-5}"

# Add date if specified
if [ -n "$MONITOR_DATE" ]; then
    ARGS="$ARGS --date $MONITOR_DATE"
fi

# Add Telegram settings if provided
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    ARGS="$ARGS --telegram-token $TELEGRAM_BOT_TOKEN"
fi

# Support multiple chat IDs (comma-separated in env var)
if [ -n "$TELEGRAM_CHAT_ID" ]; then
    OLD_IFS=$IFS
    IFS=','
    for chat_id in $TELEGRAM_CHAT_ID; do
        chat_id=$(echo "$chat_id" | xargs)  # trim whitespace
        ARGS="$ARGS --telegram-chat-id $chat_id"
    done
    IFS=$OLD_IFS
fi

# Add Email settings if provided
if [ -n "$EMAIL_SMTP_SERVER" ]; then
    ARGS="$ARGS --email-smtp-server $EMAIL_SMTP_SERVER"
fi

if [ -n "$EMAIL_SMTP_PORT" ]; then
    ARGS="$ARGS --email-smtp-port $EMAIL_SMTP_PORT"
fi

if [ -n "$EMAIL_USERNAME" ]; then
    ARGS="$ARGS --email-username $EMAIL_USERNAME"
fi

if [ -n "$EMAIL_PASSWORD" ]; then
    ARGS="$ARGS --email-password $EMAIL_PASSWORD"
fi

# Support multiple email recipients (comma-separated in env var)
if [ -n "$EMAIL_TO" ]; then
    OLD_IFS=$IFS
    IFS=','
    for email in $EMAIL_TO; do
        email=$(echo "$email" | xargs)  # trim whitespace
        ARGS="$ARGS --email-to $email"
    done
    IFS=$OLD_IFS
fi

# Run the script
exec python3 check_oodi_slots.py $ARGS

