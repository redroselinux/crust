![Screenshot](screenshot.png)
# 🐚 Crust Shell
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-linux-lightblue.svg)](https://kernel.org)
[![License](https://img.shields.io/badge/license-edited%20MIT-yellow.svg)]()
[![Made with ❤️](https://img.shields.io/badge/made%20with-%E2%9D%A4-red.svg)](https://github.com/mostypc123)

Crust is an interactive Linux shell written in Python, designed with a modern interface, AI integration, and enhanced tooling for common system tasks.

# Crust had a lot of bugs, so it is archived and we are making a new shell.

## ✨ Features

- ⚙️ Custom startup hook support via `custom_commands.py`
- 🧠 AI Assistant integration using Cohere with `.question` prompt
- 🧾 Enhanced `ls`, `lsusb`, and `df -h` commands using Rich tables
- 🔧 Built-in troubleshooting interface
- 💾 Custom integration to search for packages across multiple package managers
- 📁 Git branch and repo detection in prompt
- 🪟 Venv support and styled prompt with icons
- 🧠 Neofetch context awareness for AI assistant

## 📖 Documentation
https://crust-project.github.io/crust/

Installation:
```bash
pip install crust-shell
```

If using linux, --break-system-packages may be neccesarry to make pip actually install this. If you do not want to proceed with that, use pipx (not tested).

On Arch Linux, use AUR:
```bash
yay -S crust-git
```
Or with paru:
```bash
paru -S crust-git
```

## 🛡️ License

We use an edited version of the MIT license.

## 📫 Contributing

Contributions, bug reports, and ideas are welcome!  
Feel free to open an issue or pull request on GitHub.

## 🧑‍💻 Author

**Juraj Kollár**  
Creator of [XediX](https://github.com/mostypc123/XediX)
