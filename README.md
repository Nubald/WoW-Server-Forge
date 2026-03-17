# One Click Server Forge

A Windows GUI tool for compiling, configuring, and running World of Warcraft private servers.
Select your core, install prerequisites, compile, set up the database, and launch — all from one place.

![Platform](https://img.shields.io/badge/platform-Windows-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- **16 supported server cores** — TrinityCore, AzerothCore, cMaNGOS, MaNGOS, vMaNGOS, OregonCore, SkyFire, and more, covering Vanilla through MoP
- **Automated prerequisites** — installs Git, CMake, Visual Studio Build Tools 2022, MySQL 8, OpenSSL 3, and Boost 1.86 with one click; falls back to direct downloads if winget is unavailable
- **Source management** — clone and update server repos via Git with GitHub credential prompts fully suppressed
- **Module support** — enable/disable Eluna scripting engine, NPC Bots, AH Bot, AutoBalance, SoloCraft, and Skip DK Starting Area as Git submodules or CMake options
- **Compile** — CMake configure + MSBuild with live log streaming, parallel jobs, and a one-click CMake cache clear
- **Database setup** — full base import plus incremental SQL updates, automatic realm registration
- **Configuration editor** — edit `worldserver.conf` / `authserver.conf` / `realmd.conf` with a guided UI
- **Control panel** — start, stop, and monitor authserver + worldserver processes
- **Client info** — download links and connection instructions for every supported expansion
- **First-run wizard** — step-by-step guidance shown automatically on first launch

---

## Requirements

- Windows 10 / 11 (64-bit)
- Python 3.10 or newer — [python.org](https://www.python.org/downloads/)

All other dependencies (Git, CMake, VS Build Tools, MySQL, OpenSSL, Boost) can be installed automatically from the **Prerequisites** tab inside the app.

---

## Quick Start

```bat
git clone https://github.com/Nubald/WoW-Server-Forge.git
cd WoW-Server-Forge
setup.bat          # installs Python packages
run.bat            # launches the app
```

Or manually:

```bat
pip install -r requirements.txt
python main.py
```

---

## Supported Cores

| Core | Expansion | Version |
|------|-----------|---------|
| TrinityCore | WotLK | 3.3.5a |
| TrinityCore | Master (SL+) | latest |
| TrinityCore | Cataclysm | 4.3.4 |
| TrinityCore | WoD | 6.2.4 |
| AzerothCore | WotLK | 3.3.5a |
| AzerothCore | Cataclysm | 4.3.4 |
| cMaNGOS | Vanilla | 1.12.1 |
| cMaNGOS | TBC | 2.4.3 |
| cMaNGOS | WotLK | 3.3.5a |
| MaNGOS Zero | Vanilla | 1.12.1 |
| MaNGOS One | TBC | 2.4.3 |
| MaNGOS Two | WotLK | 3.3.5a |
| MaNGOS Three | Cataclysm | 4.3.4 |
| vMaNGOS | Vanilla | 1.12.1 |
| OregonCore | TBC | 2.4.3 |
| SkyFire | MoP | 5.4.8 |

---

## Project Structure

```
main.py                  # entry point
run.bat / setup.bat      # Windows launchers
requirements.txt
app/                     # application bootstrap & state
core/                    # business logic (build, database, modules, git, prereqs…)
models/                  # data models
services/                # event bus, logging, worker threads
ui/
  views/                 # one file per screen
  widgets/               # reusable components (sidebar, log console, wizard…)
data/
  servers/               # JSON definition per server core
  modules/               # JSON definition per optional module
  prerequisites/         # windows_requirements.json
  templates/             # config file templates
profiles/                # user profiles (git-ignored)
logs/                    # runtime logs (git-ignored)
```

---

## Contributing

Pull requests are welcome. For large changes please open an issue first.

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-change`)
3. Commit your changes
4. Open a pull request

---

## License

MIT — see [LICENSE](LICENSE) for details.
