# Notational Celerity

A platform-independent clone of Notational Velocity, built with Python and PyQt5. This app aims to replicate the design and feature set of the original Notational Velocity, including:

- Instant search-as-you-type
- Minimalist, distraction-free interface
- Note creation, editing, and deletion
- Auto-saving of notes
- Persistent storage (SQLite-based, encryption soon-ish)

Please note that this app is an optical and functional clone, not a modification or reverse engineering of Notational Velocity or it's source code (which can be found [here](https://github.com/scrod/nv/).)

## Features
- Search bar for instant filtering
- List of notes
- Rich text note editor
- Keyboard-centric navigation
- Cross-platform (macOS, GNU/Linux, Windows)

## Setup

1. Install Python 3.7+
2. Install dependencies:
   ```sh
   python3 -m pip install -r requirements.txt
   ```
3. Run the app:
   ```sh
   python3 main.py
   ```

## Building Platform-Independent Executables

### Quick Build
```sh
python3 build.py
```

### Build Options
- **macOS**: Creates `Notational Celerity` app bundle
- **GNU/Linux**: Creates `notational-celerity` executable
- **Windows**: Creates `Notational Celerity.exe`

### Clean Build Artifacts
```sh
python3 build.py clean
```

## Signing and Notarizing the App (macOS only)

To sign and notarize the `.app` bundle for macOS distribution (without security warnings and for a fast startup), feel free to use the provided automation script:

### Prerequisites
- Apple Developer Account
- Xcode and Xcode Command Line Tools (`xcode-select --install`)
- Your Apple ID added to Xcode (Xcode > Preferences > Accounts)
- App-specific password for notarization (if 2FA is enabled)
- PyInstaller-built `.app` bundle (per default `dist/Notational Celerity.app`)

### Usage
```sh
chmod +x notarize_mac.sh
./notarize_mac.sh "dist/Notational Celerity.app"
```
The script will prompt for any required information not provided as environment variables.

**Disclaimer:**
Everyone is encouraged to review the contents of `notarize_mac.sh` before running it, to understand and verify what it does.
