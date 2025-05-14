# AutoSafety Reporter Bot

A Telegram bot for the Auto Safety radio show that enables listeners to report traffic issues and interact with hosts.

## Features

- 🚗 Report traffic issues with location and description
- 🎙️ Ask questions to show hosts
- 🔁 Automatic message forwarding to admins
- 🔔 Show time reminders (optional)

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your configuration:
```
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789,987654321  # Comma-separated list of admin Telegram IDs
```

3. Run the bot:
```bash
python bot.py
```

## Usage

1. Start the bot by sending `/start`
2. Use the menu buttons to:
   - Report traffic issues
   - Ask questions
   - Subscribe to reminders
