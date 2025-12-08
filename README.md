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

1. Open [**the plugin page**](example.com).
2. Download this plugin.
3. Restart Roblox Studio.
5. In **Game Settings** -> **Security**, enable **Allow HTTP Requests**.

#### ⚠️ Local Download Is Currently Unavailable. ⚠️
```md
#### Via Local Download

1. Open **Roblox Studio**.
2. Go to the **Plugins** tab -> **Plugins Folder**.
3. Copy `PestoPlugin.server.lua` from the `Pesto/RobloxPlugin` folder into your Plugins folder.
4. Restart Roblox Studio.
5. In **Game Settings** -> **Security**, enable **Allow HTTP Requests**.
```

---

## ⚙️ Usage

Pesto allows you to bind specific folders on your computer to specific Roblox games (Universes).

1. **Create a Project Folder:**
   Create a folder where you want your game to be synced to.

2. **Start the Server:**
   Open this new folder inside your IDE of choice and run this in the terminal.

   ```bash
   pesto Server
   ```

3. **Bind & Sync:**
   * Open your game in Roblox Studio.
   * Click **Export** in the Pesto toolbar.
   * *Your game is now bound to this folder!*

4. **Live Sync:**
   * **Export:** Sends scripts from Roblox Studio -> VS Code.
   * **Import:** Sends scripts from VS Code -> Roblox Studio (updates open scripts automatically!).

## 🗑️ Uninstall

To uninstall Pesto, you can run the following command:

```bash
pesto Uninstall
```

Alternatively, if you have the repository cloned, you can run:

```bash
./uninstall.sh
```

---

## 🔒 Security

Pesto uses a `.pesto_id` file to bind a directory to a specific Roblox Universe ID. This prevents you from accidentally overwriting files from the wrong game.

## 📦 Requirements

* Python 3.9+
* Roblox Studio

## Contribution

Big thanks to the original creator of [Silicon](https://github.com/ervum/Silicon), this repository wouldnt have existed without his.
I heavily modified his repository and created my own plugin since his became unavailable.

This repository can be forked and cloned, the plugin costs money because i really need money to pay for ad credits for my upcoming game.

If i have enough robux (around 20k) then i will make this plugin free to use (of course paid users will get features faster and better)