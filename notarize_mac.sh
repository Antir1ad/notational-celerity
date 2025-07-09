#!/bin/bash
# notarize_mac.sh - Automate signing and notarizing the Notational Celerity macOS .app bundle
# Usage: ./notarize_mac.sh "dist/Notational Celerity.app"

set -e

APP_PATH="$1"
APP_NAME=$(basename "$APP_PATH")
APP_DIR=$(dirname "$APP_PATH")
ZIP_PATH="$APP_DIR/${APP_NAME%.app}.zip"

# Prompt for required info if not set
CERT_NAME="${CERT_NAME:-}" # e.g. Developer ID Application: Your Name (TEAMID)
APPLE_ID="${APPLE_ID:-}"   # Your Apple ID email
TEAM_ID="${TEAM_ID:-}"     # Your Apple Developer Team ID
APP_SPECIFIC_PASSWORD="${APP_SPECIFIC_PASSWORD:-}" # App-specific password
BUNDLE_ID="${BUNDLE_ID:-com.hyperborea.notationalcelerity}" # Default bundle ID

if [ -z "$APP_PATH" ] || [ ! -d "$APP_PATH" ]; then
  echo "Usage: $0 \"path/to/YourApp.app\""
  exit 1
fi

if [ -z "$CERT_NAME" ]; then
  read -p "Enter your Developer ID Application certificate name: " CERT_NAME
fi
if [ -z "$APPLE_ID" ]; then
  read -p "Enter your Apple ID email: " APPLE_ID
fi
if [ -z "$TEAM_ID" ]; then
  read -p "Enter your Apple Developer Team ID: " TEAM_ID
fi
if [ -z "$APP_SPECIFIC_PASSWORD" ]; then
  read -s -p "Enter your app-specific password: " APP_SPECIFIC_PASSWORD
  echo
fi
if [ -z "$BUNDLE_ID" ]; then
  read -p "Enter your app bundle identifier (e.g. com.example.notationalcelerity): " BUNDLE_ID
fi

# 1. Sign the app
set -x
codesign --deep --force --verify --verbose \
  --sign "$CERT_NAME" \
  "$APP_PATH"
set +x

echo "[✔] App signed."

# 2. Verify signature
codesign --verify --deep --strict --verbose=2 "$APP_PATH"
spctl --assess --type execute --verbose "$APP_PATH"
echo "[✔] Signature verified."

# 3. Zip the app
set -x
ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"
set +x
echo "[✔] App zipped at $ZIP_PATH."

# 4. Submit for notarization
set -x
UUID=$(xcrun altool --notarize-app \
  --primary-bundle-id "$BUNDLE_ID" \
  --username "$APPLE_ID" \
  --password "$APP_SPECIFIC_PASSWORD" \
  --team-id "$TEAM_ID" \
  --file "$ZIP_PATH" 2>&1 | awk '/RequestUUID/ {print $3}')
set +x
if [ -z "$UUID" ]; then
  echo "[✗] Notarization submission failed."
  exit 1
fi
echo "[✔] Submitted for notarization. RequestUUID: $UUID"

echo "Waiting for notarization to complete... (this may take a few minutes)"
while true; do
  STATUS=$(xcrun altool --notarization-info "$UUID" \
    --username "$APPLE_ID" \
    --password "$APP_SPECIFIC_PASSWORD" 2>&1)
  if echo "$STATUS" | grep -q 'success'; then
    echo "[✔] Notarization succeeded."
    break
  elif echo "$STATUS" | grep -q 'in progress'; then
    sleep 20
  else
    echo "$STATUS"
    echo "[✗] Notarization failed."
    exit 1
  fi
done

# 5. Staple the ticket
set -x
xcrun stapler staple "$APP_PATH"
set +x
echo "[✔] Stapled notarization ticket."

# 6. Final verification
spctl --assess --type execute --verbose "$APP_PATH"
echo "[✔] App is ready for distribution!" 