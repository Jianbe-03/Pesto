#!/bin/bash

set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Define installation directory
INSTALL_DIR="$HOME/.pesto"
BIN_DIR="/usr/local/bin"

echo "Installing Pesto globally..."

# Create installation directory
mkdir -p "$INSTALL_DIR"

# Copy files from the script's directory
echo "Copying files from $SCRIPT_DIR..."
OS_NAME="$(uname -s)"
EXE_SRC=""
if [ "$OS_NAME" = "Darwin" ]; then
    EXE_SRC="$SCRIPT_DIR/dist/Pesto-mac"
else
    EXE_SRC="$SCRIPT_DIR/dist/Pesto-linux"
fi

# Backward-compatible fallback
if [ ! -f "$EXE_SRC" ]; then
    if [ -f "$SCRIPT_DIR/dist/Pesto" ]; then
        EXE_SRC="$SCRIPT_DIR/dist/Pesto"
    fi
fi

if [ ! -f "$EXE_SRC" ]; then
    echo "Error: Pesto executable not found in $SCRIPT_DIR/dist"
    echo "Expected one of: Pesto-mac, Pesto-linux (or legacy Pesto)"
    exit 1
fi

# Remove any previous install artifacts first (prevents recursion issues)
rm -f "$INSTALL_DIR/Pesto-mac" "$INSTALL_DIR/pesto"

# Copy to a temp path first, then atomically move into place
TMP_EXE="$INSTALL_DIR/Pesto.tmp"
rm -f "$TMP_EXE"
cp "$EXE_SRC" "$TMP_EXE"
chmod +x "$TMP_EXE"

# Remove macOS quarantine if present
if command -v xattr >/dev/null 2>&1; then
    xattr -d com.apple.quarantine "$TMP_EXE" 2>/dev/null || true
fi

# Validate size/type so we don't accidentally install a wrapper script
EXE_SIZE=$(stat -f%z "$TMP_EXE" 2>/dev/null || stat -c%s "$TMP_EXE" 2>/dev/null || echo 0)
if [ "$EXE_SIZE" -lt 1000000 ]; then
    echo "Error: Installed executable is too small ($EXE_SIZE bytes)."
    echo "Make sure you put the real PyInstaller binary in $SCRIPT_DIR/dist (expected ~8-12MB)."
    rm -f "$TMP_EXE"
    exit 1
fi

if command -v file >/dev/null 2>&1; then
    FILE_INFO="$(file -b "$TMP_EXE" || true)"
    case "$OS_NAME" in
        Darwin)
            echo "$FILE_INFO" | grep -q "Mach-O" || {
                echo "Error: Expected a Mach-O binary but got: $FILE_INFO"
                rm -f "$TMP_EXE"
                exit 1
            }
            ;;
        Linux)
            echo "$FILE_INFO" | grep -q "ELF" || {
                echo "Error: Expected an ELF binary but got: $FILE_INFO"
                rm -f "$TMP_EXE"
                exit 1
            }
            ;;
    esac
fi

mv -f "$TMP_EXE" "$INSTALL_DIR/Pesto-mac"

cp "$SCRIPT_DIR/Settings.yaml" "$INSTALL_DIR/"

# Create wrapper script for the executable
cat <<EOF > "$INSTALL_DIR/pesto"
#!/bin/bash
exec "$INSTALL_DIR/Pesto-mac" "\$@"
EOF

# Make wrapper executable
chmod +x "$INSTALL_DIR/pesto"

# Create symlink in /usr/local/bin
if [ -d "$BIN_DIR" ]; then
    if [ -f "$BIN_DIR/pesto" ]; then
        sudo rm "$BIN_DIR/pesto"
    fi
    sudo ln -s "$INSTALL_DIR/pesto" "$BIN_DIR/pesto"
    echo "Pesto installed to $BIN_DIR/pesto"
else
    # If /usr/local/bin doesn't exist, check if we already added to PATH
    if ! grep -q "$INSTALL_DIR" ~/.zshrc; then
        echo "Warning: $BIN_DIR does not exist."
        echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> ~/.zshrc
        echo "Added $INSTALL_DIR to PATH in ~/.zshrc"
        echo "Please restart your terminal or run 'source ~/.zshrc' to use the command."
    else
        echo "$INSTALL_DIR is already in your PATH."
    fi
fi

echo "Installation complete!"
echo "You can now run 'pesto Server' in any directory to start syncing for that folder."
