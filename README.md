<div align="center">

# Zenith
**High-Performance Discord Security, Governance & Server Automation System**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.3+-5865F2?style=flat-square&logo=discord&logoColor=white)](https://github.com/Rapptz/discord.py)
[![License: MIT](https://img.shields.io/badge/License-MIT-success?style=flat-square)](LICENSE)
[![Discord](https://img.shields.io/badge/Discord-shree.ltc-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/users/1465912900710305822)

A modular, enterprise-grade Discord bot engine built for high-throughput communities. Features real-time audit log anti-nuke protection, zero-downtime hot-reloads, hybrid PostgreSQL/SQLite data storage, interactive button components, and an extensive administration suite.

[Features](#-core-features) • [Installation](#-installation--setup) • [Architecture](#-system-architecture) • [Command Manual](#-command-modules) • [License](#-license)

</div>

---

## ⚡ Core Features

* **🛡️ Military-Grade Antinuke & Anti-Raid**:
  * Real-time audit log scanner intercepting unauthorized bans, kicks, channel purges, role tampering, rogue bot additions, and webhook hijacking.
  * Instant offender ban/kick execution and automatic restoration of deleted channels and unbanned members.
  * Granular administrator whitelist system with immunity flags.
* **⚙️ Intelligent Automod Engine**:
  * Low-latency message evaluation for rapid chat spam, unauthorized Discord invite links, external URLs, excessive capitalization, and mass mentions.
  * Configurable penalties (instant message deletion, automated 5-minute timeouts, or kicks).
* **🔨 Complete Moderation & Governance**:
  * Bans, softbans, timeouts, warnings with database infraction tracking, channel locks, and hide modes.
  * Multi-filter purges (all, bots, links, user, contains) and bulk role assignment (humans, bots).
* **🎫 Interactive Support Ticket Panels**:
  * Persistent Discord button panels generating private ticket channels with granular permissions.
  * Staff claim workflows and automated text transcript delivery to the user's DMs upon ticket closure.
* **🔊 Dynamic TempVC (Join-to-Create)**:
  * Generates private customizable voice channels when members join a designated hub.
  * Room owner controls: lock, unlock, rename, user limits, permit, reject, and auto-cleanup upon desertion.
* **👋 Onboarding & Autoroles**:
  * Dynamic welcome greetings with custom member count placeholders and automated role assignment for humans and bots.
* **🪙 Virtual Community Economy**:
  * Wallets, bank vaults, daily dividends, shift work, peer-to-peer cash transfers, casino slot machines, and guild wealth leaderboards.
* **🔄 Resilient Dual-Layer Architecture**:
  * Supports high-throughput **PostgreSQL (`asyncpg`)** and **Redis**, while automatically falling back to **local SQLite (`aiosqlite`)** and in-memory TTL caching when external databases aren't hosted.

---

## 🚀 Installation & Setup

### Prerequisites
* Python 3.10 or higher
* A Discord Bot Token from the [Discord Developer Portal](https://discord.com/developers/applications) with all **Privileged Gateway Intents** (Message Content, Server Members, Presence) toggled ON.

### Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/shree-ltc/zenith.git
   cd zenith
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in your credentials:
   ```ini
   BOT_TOKEN=your_token_here
   BOT_PREFIX=z!
   OWNER_IDS=1465912900710305822
   ```

5. **Start Zenith**:
   ```bash
   python3 main.py
   ```

---

## 🏛️ System Architecture

```
zenith/
├── core/
│   ├── bot.py             # Custom AutoShardedBot with dynamic prefixes & extension discovery
│   ├── config.py          # Strongly typed environment configuration
│   ├── database.py        # Hybrid asyncpg + aiosqlite + Redis engine
│   ├── errors.py          # Unified global exception and permission handler
│   └── logging.py         # Colorized ANSI console & rotating file loggers
├── ui/
│   ├── colors.py          # Consistent Midnight & Blurple palette
│   ├── embeds.py          # Standardized ZenithEmbed factory
│   └── views.py           # Reusable Paginators & Confirmation Modals
├── cogs/
│   ├── antinuke.py        # Audit log anti-raid & mass modification shield
│   ├── automod.py         # Real-time regex & burst spam filters
│   ├── moderation.py      # Bans, timeouts, warnings, channel locks, multi-purges
│   ├── tickets.py         # Persistent button ticket panels & transcripts
│   ├── voice.py           # Join-to-create voice channels (TempVC)
│   ├── welcome.py         # Member greetings & human/bot autoroles
│   ├── economy.py         # Virtual banking, work shifts, slots, leaderboards
│   ├── server.py          # Channel nuke, server-wide lockdown, dehoist
│   ├── utility.py         # Deep user, server, avatar, and snipe analytics
│   ├── logs.py            # Real-time message edit/delete and member audit logs
│   ├── giveaways.py       # Timed drawings with live button entry
│   ├── afk.py             # Away status with automated mention alerts
│   ├── fun.py             # Interactive Rock-Paper-Scissors, 8ball, coinflips
│   ├── owner.py           # Hot-reloads, slash syncing, and remote eval
│   └── help.py            # Categorized dropdown menu manual
├── requirements.txt
├── .env.example
├── .gitignore
└── LICENSE
```

---

## 📖 Command Modules

| Category | Key Commands | Purpose |
| :--- | :--- | :--- |
| **🛡️ Antinuke** | `antinuke enable`, `antinuke punishment`, `antinuke whitelist`, `antinuke logs` | Intercepts rogue admin attacks in real-time. |
| **⚙️ Automod** | `automod antispam`, `automod antilinks`, `automod antiinvites`, `automod anticaps` | Filters illicit messages and chat spam. |
| **🔨 Moderation** | `ban`, `softban`, `kick`, `timeout`, `warn`, `lock`, `hide`, `purge`, `role` | Server moderation with strict hierarchy validation. |
| **🎫 Tickets** | `ticket setup`, `ticket close`, `ticket claim`, `ticket add` | Private support channels with transcript export. |
| **🔊 TempVC** | `voice lock`, `voice unlock`, `voice rename`, `voice limit`, `voice permit` | Join-to-create customizable voice rooms. |
| **👋 Welcome** | `welcome channel`, `welcome message`, `autorole human`, `autorole bot` | Member onboarding and initial role assignment. |
| **🪙 Economy** | `balance`, `daily`, `work`, `deposit`, `withdraw`, `pay`, `slots`, `leaderboard` | Virtual currency and banking mini-games. |
| **📊 Utility** | `userinfo`, `serverinfo`, `avatar`, `botinfo`, `ping`, `snipe`, `editsnipe` | Server intelligence and diagnostics. |
| **🎉 Giveaways** | `giveaway start <time> <winners> <prize>`, `giveaway reroll` | Automated community drawings. |
| **💤 AFK** | `afk [reason]` | Notifies users who mention you while away. |
| **👑 Developer** | `reloadall`, `sync`, `eval`, `prefix` | Zero-downtime hot reloading and maintenance. |

---

## 🔒 Security Best Practices

1. **Role Positioning**: Ensure Zenith's role is positioned as high as possible in the Server Settings role hierarchy so it can manage subordinate roles and moderate members without hierarchy exceptions.
2. **Audit Permissions**: Grant the bot `View Audit Log`, `Manage Channels`, `Manage Roles`, `Ban Members`, and `Kick Members` for the Antinuke system to operate effectively.
3. **Environment Security**: Never commit your `.env` file or bot token to public version control.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details. Built with ❤️ by [shree-ltc](https://github.com/shree-ltc).
