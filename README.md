# ✨ Pesto

**A powerful, Roblox Studio to VS Code synchronization tool.**

## 🚀 Installation

### Prerequisites

Before installing Pesto, ensure you have the following:

*   **Python 3.9 or higher** - Download from [python.org](https://www.python.org/downloads/)
*   **Git** - Download from [git-scm.com](https://git-scm.com/downloads)
*   **VS Code (or other IDE)** - Download from [code.visualstudio.com](https://code.visualstudio.com/)
*   **Roblox Studio** - Download from the Roblox website

### 1. Install the CLI Tool

#### On Windows

1.  Open **PowerShell** as Administrator (search for PowerShell in Start menu, right-click and select "Run as administrator").

2.  Install Pesto by running:
    ```powershell
    git clone https://github.com/Jianbe-03/Pesto
    cd Pesto
    .\install.ps1
    ```

    This will:
    *   Create a virtual environment
    *   Install Python dependencies (`requests`, `pyyaml`)
    *   Add `pesto` to your PATH

3.  Restart PowerShell or open a new terminal window to use the `pesto` command.

#### On macOS

1.  Open **Terminal**.

2.  Install Pesto by running:
    ```bash
    git clone https://github.com/Jianbe-03/Pesto
    cd Pesto
    ./install.sh
    ```

    This will install `pesto` as a global command.

#### On Linux

1.  Open your terminal.

2.  Install Pesto by running:
    ```bash
    git clone https://github.com/Jianbe-03/Pesto
    cd Pesto
    ./install.sh
    ```

### 2. Install the Roblox Plugin

Pesto requires a companion plugin in Roblox Studio to communicate with your computer.

1.  **[Get the Pesto Plugin here](https://create.roblox.com/store/asset/124198645621974/Pesto)**.
   *   *Why is it paid?* I'm an indie developer trying to fund ad credits for my upcoming game. Your support helps me keep building cool tools! Once I reach my goal, I plan to make a free version available.
2.  In Roblox Studio, go to **Game Settings** -> **Security** and enable **Allow HTTP Requests**.

### 3. Install the VS Code Extension (Optional but Recommended)

For the best experience, install the Pesto Explorer extension:

1.  Open VS Code.
2.  Go to Extensions (Ctrl+Shift+X).
3.  Search for "Pesto Roblox Project Explorer".
4.  Install and reload VS Code.

This extension provides:
*   A Roblox-style file explorer with official icons
*   Smart sorting (Services first, then classes)
*   Visual property editor
*   Auto-refresh when files change

---

## ⚙️ Usage

1.  **Create a Project Folder:**
    Make a folder on your computer where you want your game code to live.

2.  **Start the Server:**
   Open that folder in VS Code (or your terminal or any other IDE with a terminal) and run:
   ```bash
   pesto Server
   ```

3.  **Connect:**
    *   Open your game in Roblox Studio.
    *   Click **Export** in the Pesto plugin toolbar.
    *   *Done! Your game is now linked.*

4.  **Workflow:**
    *   **Export:** Pulls changes from Roblox Studio to VS Code.
    *   **Import:** Pushes changes from VS Code to Roblox Studio.

---

## 🗑️ Uninstall

To uninstall Pesto, simply run:

```bash
pesto Uninstall
```

---

## 🔄 Update

To update Pesto to the latest version, run:

```bash
pesto Update
```

---

## 🔒 Security

Pesto uses a `.pesto_id` file to bind a directory to a specific Roblox Universe ID. This prevents you from accidentally overwriting files from the wrong game.

## 📦 Requirements

*   Python 3.9+
*   Roblox Studio
*   VS Code (recommended)
*   Git

## 🤝 Contribution & Credits

Big thanks to the original creator of [Silicon](https://github.com/ervum/Silicon) for the inspiration. Pesto is a heavily modified and evolved version designed for modern workflows.

**Support the project:** Buying the plugin on Roblox Studio directly supports the development of this tool and my future games. Thank you! ❤️