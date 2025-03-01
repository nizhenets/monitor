# Monitor Script

This script automates the process of downloading and setting up necessary files with real-time status updates via Discord webhooks.

## Features

- Downloads Python.zip from GitHub repository
- Downloads and installs 7-Zip
- Extracts Python.zip using 7-Zip
- Sends real-time status updates to a Discord webhook
- Uses a queue system to send messages with 2-second intervals
- Cleans up temporary files after completion

## Requirements

- Windows OS
- Internet connection
- Discord webhook URL (configured in the script)

## How it Works

1. The script sets up a webhook queue system that sends messages at 2-second intervals
2. Downloads Python.zip and 7-Zip installer to the %appdata% folder
3. Installs 7-Zip with appropriate waiting periods
4. Extracts Python.zip using the installed 7-Zip
5. Cleans up temporary files
6. Reports all actions via Discord webhook

## Usage

Simply run the `monitor.cmd` file as administrator for proper installation.
