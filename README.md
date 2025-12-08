# ✨ Pesto

**A powerful, Roblox Studio to VS Code synchronization tool.**

## 🚀 Installation

### 1. Install the CLI Tool

Open your terminal and run:

```bash
git clone https://github.com/Jianbe-03/Pesto
cd Pesto
./install.sh
```

This will install `pesto` as a global command on your system.

### 2. Install the Roblox Plugin

#### Via Roblox Website

1. Open **example.com**.
2. Download this plugin.
3. Restart Roblox Studio.
5. In **Game Settings** -> **Security**, enable **Allow HTTP Requests**.

#### Via Local Download

1. Open **Roblox Studio**.
2. Go to the **Plugins** tab -> **Plugins Folder**.
3. Copy `PestoPlugin.server.lua` from the `Pesto/RobloxPlugin` folder into your Plugins folder.
4. Restart Roblox Studio.
5. In **Game Settings** -> **Security**, enable **Allow HTTP Requests**.

---

## ⚙️ Usage

Pesto allows you to bind specific folders on your computer to specific Roblox games (Universes).

1. **Create a Project Folder:**
   ```bash
   mkdir MyGame
   cd MyGame
   ```

2. **Start the Server:**
   ```bash
   pesto Server
   ```

3. **Bind & Sync:**
   * Open your game in Roblox Studio.
   * Click **Export** in the Pesto toolbar.
   * *Your game is now bound to this folder!*

4. **Live Sync:**
   * **Export:** Sends scripts from Studio -> VS Code.
   * **Import:** Sends scripts from VS Code -> Studio (updates open scripts automatically!).

---

## 🔒 Security

Pesto uses a `.pesto_id` file to bind a directory to a specific Roblox Universe ID. This prevents you from accidentally overwriting files from the wrong game.

## 📦 Requirements

* Python 3.9+
* Roblox Studio

## Contribution

Big thanks to the original creator of [Silicon](https://github.com/ervum/Silicon), this repository wouldnt have existed without his.