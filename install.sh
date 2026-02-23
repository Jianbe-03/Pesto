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
if [ "$OS_NAME" = "Darwin" ]; then
    EXE_NAME="Pesto-mac"
else
    EXE_NAME="Pesto-linux"
fi

# Remove any previous install artifacts first (prevents recursion issues)
rm -rf "$INSTALL_DIR/$EXE_NAME" "$INSTALL_DIR/pesto"

EXE_SRC="$SCRIPT_DIR/dist/$EXE_NAME"

if [ -f "$EXE_SRC" ]; then
    # Onefile build: copy the single executable
    cp "$EXE_SRC" "$INSTALL_DIR/$EXE_NAME"
    EXE_PATH="$INSTALL_DIR/$EXE_NAME"
elif [ -d "$EXE_SRC" ]; then
    # Onedir build: copy the entire folder
    cp -r "$EXE_SRC" "$INSTALL_DIR/$EXE_NAME"
    EXE_PATH="$INSTALL_DIR/$EXE_NAME/$EXE_NAME"

    # Remove the helpers folder if it exists (we install the correct helper manually)
    if [ -d "$INSTALL_DIR/$EXE_NAME/helpers" ]; then
        rm -rf "$INSTALL_DIR/$EXE_NAME/helpers"
    fi
else
    echo "Error: Pesto build not found at $EXE_SRC"
    exit 1
fi

# Validate size/type so we don't accidentally install a wrapper script
EXE_SIZE=$(stat -f%z "$EXE_PATH" 2>/dev/null || stat -c%s "$EXE_PATH" 2>/dev/null || echo 0)
if [ "$EXE_SIZE" -lt 1000000 ]; then
    echo "Error: Installed executable is too small ($EXE_SIZE bytes)."
    echo "Make sure you put the real PyInstaller binary in $SCRIPT_DIR/dist (expected ~8-12MB)."
    rm -rf "$INSTALL_DIR/$EXE_NAME"
    exit 1
fi

if command -v file >/dev/null 2>&1; then
    FILE_INFO="$(file -b "$EXE_PATH" || true)"
    case "$OS_NAME" in
        Darwin)
            echo "$FILE_INFO" | grep -q "Mach-O" || {
                echo "Error: Expected a Mach-O binary but got: $FILE_INFO"
                rm -rf "$INSTALL_DIR/$EXE_NAME"
                exit 1
            }
            ;;
        Linux)
            echo "$FILE_INFO" | grep -q "ELF" || {
                echo "Error: Expected an ELF binary but got: $FILE_INFO"
                rm -rf "$INSTALL_DIR/$EXE_NAME"
                exit 1
            }
            ;;
    esac
fi

# Remove macOS quarantine if present
if command -v xattr >/dev/null 2>&1; then
    xattr -d com.apple.quarantine "$EXE_PATH" 2>/dev/null || true
fi

# Make executable
chmod +x "$EXE_PATH"

if [ -d "$INSTALL_DIR/$EXE_NAME" ]; then
    cp "$SCRIPT_DIR/Settings.yaml" "$INSTALL_DIR/$EXE_NAME/"
    cp "$SCRIPT_DIR/Agents.md" "$INSTALL_DIR/$EXE_NAME/"
else
    cp "$SCRIPT_DIR/Settings.yaml" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/Agents.md" "$INSTALL_DIR/"
fi

# Copy native helper binary (for high-performance operations)
echo "Installing native helper..."
if [ "$OS_NAME" = "Darwin" ]; then
    # Detect architecture for macOS
    ARCH="$(uname -m)"
    if [ "$ARCH" = "arm64" ]; then
        HELPER_SRC="$SCRIPT_DIR/pesto-helper-darwin-arm64"
    elif [ "$ARCH" = "x86_64" ] || [ "$ARCH" = "amd64" ]; then
        HELPER_SRC="$SCRIPT_DIR/pesto-helper-darwin-amd64"
    else
        echo "Warning: Unknown architecture '$ARCH', defaulting to amd64"
        HELPER_SRC="$SCRIPT_DIR/pesto-helper-darwin-amd64"
    fi
    echo "Detected macOS architecture: $ARCH -> $(basename "$HELPER_SRC")"
else
    HELPER_SRC="$SCRIPT_DIR/pesto-helper-linux-amd64"
fi

if [ -f "$HELPER_SRC" ]; then
    if [ -d "$INSTALL_DIR/$EXE_NAME" ]; then
        cp "$HELPER_SRC" "$INSTALL_DIR/$EXE_NAME/"
        HELPER_DEST="$INSTALL_DIR/$EXE_NAME/$(basename "$HELPER_SRC")"
    else
        cp "$HELPER_SRC" "$INSTALL_DIR/"
        HELPER_DEST="$INSTALL_DIR/$(basename "$HELPER_SRC")"
    fi
    
    chmod +x "$HELPER_DEST"
    # Remove macOS quarantine if present
    if command -v xattr >/dev/null 2>&1; then
        xattr -d com.apple.quarantine "$HELPER_DEST" 2>/dev/null || true
    fi
    echo "Installed native helper: $(basename "$HELPER_SRC")"
else
    echo "Warning: Native helper not found at $HELPER_SRC"
    echo "Pesto will use Python fallback (slower for large projects)"
fi

# Create wrapper script for the executable
cat <<EOF > "$INSTALL_DIR/pesto"
#!/bin/bash
exec "$EXE_PATH" "\$@"
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
