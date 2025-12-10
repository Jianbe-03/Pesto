# ✨ Pesto

**A powerful, Roblox Studio to VS Code synchronization tool.**

## 🚀 Installation

### 1. Install the CLI Tool

#### On MacOs

Open your terminal and run:

```bash
git clone https://github.com/Jianbe-03/Pesto
cd Pesto
./install.sh
```

#### On Windows

Open your terminal and run:

```shell
git clone https://github.com/Jianbe-03/Pesto
cd Pesto
./install.ps1
```

This will install `pesto` as a global command on your system.

### 2. Install the Roblox Plugin

Pesto requires a companion plugin in Roblox Studio to communicate with your computer.

1.  **[Get the Pesto Plugin here](https://create.roblox.com/store/asset/124198645621974/Pesto)**.
   *   *Why is it paid?* I'm an indie developer trying to fund ad credits for my upcoming game. Your support helps me keep building cool tools! Once I reach my goal, I plan to make a free version available.
2.  In Roblox Studio, go to **Game Settings** -> **Security** and enable **Allow HTTP Requests**.

---

## ⚙️ Usage

Pesto allows you to bind specific folders on your computer to specific Roblox games (Universes).

1. **Create a Project Folder:**
   Make a folder on your computer where you want your game to be synced to.

2.  **Start the Server:**
   Open that folder in VS Code (or your terminal or any other IDE with a terminal) and run:
   ```bash
   pesto Server
   ```

3. **Bind & Sync:**
   * Open your game in Roblox Studio.
   * Click **Export** in the Pesto plugin toolbar.
   * *Your game is now bound to this folder!*

4.  **Workflow:**
   *   **Export:** Pulls changes from Roblox Studio to VS Code.
   *   **Import:** Pushes changes from VS Code to Roblox Studio.

---

## 🗑️ Uninstall

To uninstall Pesto, simply run:

```bash
pesto Uninstall
```

## 🔄 Update

To update Pesto to the latest version, run:

```bash
pesto Update
```

---

## 🔒 Security

Pesto uses a `.pesto_id` file to bind a directory to a specific Roblox Universe ID. This prevents you from accidentally overwriting files from the wrong game.

## 📦 Requirements

* Python 3.9+
* Roblox Studio

## 🤝 Contribution & Credits

Big thanks to the original creator of [Silicon](https://github.com/ervum/Silicon), this repository wouldnt have existed without his.
I heavily modified his repository and created my own plugin since his became unavailable.

This repository can be forked and cloned, the plugin costs money because i really need money to pay for ad credits for my upcoming game.

If i have enough robux (around 20k) then i will make this plugin free to use (of course paid users will get features faster and better)