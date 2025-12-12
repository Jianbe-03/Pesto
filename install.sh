#!/bin/bash

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
cp "$SCRIPT_DIR/Pesto.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/Settings.yaml" "$INSTALL_DIR/"

# Create a virtual environment to avoid PEP 668 errors
echo "Creating virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"

# Install dependencies into the virtual environment
echo "Installing dependencies..."
"$INSTALL_DIR/venv/bin/pip" install requests pyyaml watchdog

# Create wrapper script using the venv python
cat <<EOF > "$INSTALL_DIR/pesto"
#!/bin/bash
"$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/Pesto.py" "\$@"
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
