#!/bin/bash

# Define installation directory
INSTALL_DIR="$HOME/.pesto"
BIN_DIR="/usr/local/bin"

echo "Uninstalling Pesto..."

# 1. Remove installation directory
if [ -d "$INSTALL_DIR" ]; then
    echo "Removing installation directory $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
else
    echo "Installation directory $INSTALL_DIR not found."
fi

# 2. Remove symlink
if [ -L "$BIN_DIR/pesto" ] || [ -f "$BIN_DIR/pesto" ]; then
    echo "Removing symlink $BIN_DIR/pesto..."
    sudo rm "$BIN_DIR/pesto"
else
    echo "Symlink $BIN_DIR/pesto not found."
fi

# 3. Remove from PATH in .zshrc
SHELL_RC="$HOME/.zshrc"
if [ -f "$SHELL_RC" ]; then
    # Check if the path is in the file
    if grep -q ".pesto" "$SHELL_RC"; then
        echo "Removing Pesto from PATH in $SHELL_RC..."
        # Create a backup
        cp "$SHELL_RC" "$SHELL_RC.pesto_uninstall_bak"
        
        # Remove lines containing .pesto
        # macOS sed requires -i '' for in-place editing
        sed -i '' '/\.pesto/d' "$SHELL_RC"
        
        echo "Removed from $SHELL_RC. Backup saved to $SHELL_RC.pesto_uninstall_bak"
        echo "Please restart your terminal or run 'source $SHELL_RC' to apply changes."
    else
        echo "Pesto path configuration not found in $SHELL_RC."
    fi
fi

echo "Uninstallation complete!"
echo "Note: If you installed the Roblox Plugin manually, please remove 'PestoPlugin.server.lua' from your Roblox Studio Plugins folder."
