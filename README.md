# Zenith

**High-Performance Discord Security & Server Automation Architecture**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.3+-5865F2?style=flat-square&logo=discord&logoColor=white)](https://github.com/Rapptz/discord.py)
[![License: MIT](https://img.shields.io/badge/License-MIT-success?style=flat-square)](LICENSE)
[![Discord](https://img.shields.io/badge/Discord-shree.ltc-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/users/1465912900710305822)

Zenith is a modular, high-throughput Discord bot engine designed for community security, automated moderation, and server management. Built with asynchronous Python (`discord.py` 2.x), it provides real-time audit log analysis for anti-nuke defense, interactive UI components, and hybrid database storage.

---

## Features

### Security & Antinuke
* **Audit Log Analysis**: Real-time monitoring intercepting unauthorized bans, kicks, channel modifications, role tampering, and rogue bot additions.
* **Instant Containment**: Enforces automatic offender punishments (ban/kick) and recovers modified channels and banned accounts.
* **Whitelist Registry**: Dedicated immunity lists for server owners and trusted staff members.

### Automod
* **Content Filtering**: Filters spam bursts, Discord server invite links, external URLs, excessive capitalization, and mass mentions.
* **Custom Sanctions**: Automated timeouts (5 minutes) or message deletions based on guild preferences.

### Moderation
* **Member Actions**: Ban, softban, kick, timeout, and warning infractions stored in the database.
* **Channel Controls**: Channel lockdown, hide/unhide toggles, and slowmode controls.
* **Message Purging**: Multi-filter purge commands (bots, links, user-specific, or keyword match up to 500 messages).
* **Role Utilities**: Bulk role assignment for humans and bots.

### Infrastructure & Community Tools
* **Support Tickets**: Button-driven ticket creation panels, private channel permissions, staff claiming, and `.txt` transcript delivery to direct messages.
* **Temporary Voice (TempVC)**: Join-to-create voice hub with automated creation and empty room deletion. Room owners can lock, limit, rename, and permit users.
* **Member Onboarding**: Customizable welcome announcements with member counters and automated initial roles.
* **Virtual Economy**: Balances, banking, work shifts, transfers, slot game, and server leaderboards.
* **Server Administration**: Channel recreation (nuke), server-wide lockdowns, and bulk nickname dehoisting.

### Architecture & Resilience
* **Dual Database Engine**: High-performance PostgreSQL (`asyncpg`) with automatic fallback to local SQLite (`aiosqlite`).
* **Caching Layer**: Redis support with in-memory TTL caching fallback.
* **Logging System**: ANSI colorized console logs and rotating file logs (`logs/zenith.log`).

---

## Installation & Setup

### Prerequisites
* Python 3.10+
* Discord Bot Token with all Privileged Gateway Intents enabled (Message Content, Server Members, Presence) in the Discord Developer Portal.

### Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/shree-ltc/zenith.git
   cd zenith
   ```

2. **Set up a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   ```
   Add your Discord bot token and user ID to `.env`:
   ```ini
   BOT_TOKEN=your_token_here
   BOT_PREFIX=z!
   OWNER_IDS=1465912900710305822
   ```

5. **Start the bot**:
   ```bash
   python3 main.py
   ```

---

## Project Structure

```
zenith/
├── core/
│   ├── bot.py             # Custom AutoShardedBot client and extension loader
│   ├── config.py          # Typed environment settings loader
│   ├── database.py        # Database abstraction (PostgreSQL / SQLite / Redis)
│   ├── errors.py          # Global command error handling
│   └── logging.py         # Console formatter and rotating file logger
├── ui/
│   ├── colors.py          # UI color constants
│   ├── embeds.py          # ZenithEmbed formatting helper
│   └── views.py           # Paginator and confirmation views
├── cogs/
│   ├── antinuke.py        # Anti-raid and audit log protection
│   ├── automod.py         # Regex message scanner and burst limiter
│   ├── moderation.py      # Sanctions, warnings, locks, and purges
│   ├── tickets.py         # Support ticket panels and transcripts
│   ├── voice.py           # Join-to-create temporary voice channels
│   ├── welcome.py         # Member greetings and autoroles
│   ├── economy.py         # Balances, work shifts, and leaderboards
│   ├── server.py          # Channel nuke, lockdowns, and dehoist
│   ├── utility.py         # User, server, avatar, and system lookups
│   ├── logs.py            # Message edit/delete and member audit logs
│   ├── giveaways.py       # Prize drawings with button entry
│   ├── afk.py             # Away status and mention notifications
│   ├── fun.py             # RPS, 8ball, coinflips, and quotes
│   ├── owner.py           # Hot-reloads, slash syncing, and eval
│   └── help.py            # Categorized help menu
├── requirements.txt
├── .env.example
├── .gitignore
└── LICENSE
```

---

## Command Reference

| Category | Primary Commands | Description |
| :--- | :--- | :--- |
| **Security** | `antinuke enable`, `antinuke punishment`, `antinuke whitelist` | Intercepts unauthorized server modifications. |
| **Automod** | `automod antispam`, `automod antilinks`, `automod antiinvites` | Filters spam, invites, and external links. |
| **Moderation** | `ban`, `softban`, `kick`, `timeout`, `warn`, `lock`, `purge` | Member management and chat regulation. |
| **Tickets** | `ticket setup`, `ticket close`, `ticket claim`, `ticket add` | Private support channels with transcript export. |
| **Voice** | `voice lock`, `voice unlock`, `voice rename`, `voice limit` | Dynamic join-to-create temporary channels. |
| **Welcome** | `welcome channel`, `welcome message`, `autorole human` | Member greetings and initial role allocation. |
| **Economy** | `balance`, `daily`, `work`, `deposit`, `withdraw`, `pay` | Virtual currency and banking mini-games. |
| **Server** | `nuke`, `lockdown`, `unlockdown`, `dehoist`, `inrole` | Guild maintenance and administrative actions. |
| **Utility** | `userinfo`, `serverinfo`, `avatar`, `botinfo`, `ping`, `snipe` | Information lookup and diagnostics. |
| **Giveaways** | `giveaway start <duration> <winners> <prize>` | Timed community prize drawings. |
| **AFK** | `afk [reason]` | Notifies users who mention you while away. |
| **Developer** | `reloadall`, `sync`, `eval`, `prefix` | Maintenance and hot-reloading. |

---

## Configuration Guidelines

1. **Hierarchy**: Position Zenith's role above the roles it manages in the Server Settings so that moderation commands and role toggles succeed without hierarchy restrictions.
2. **Permissions**: Required bot permissions include `View Audit Log`, `Manage Channels`, `Manage Roles`, `Ban Members`, and `Kick Members`.
3. **Security**: Keep your `.env` file private and never commit tokens to public repositories.

---

## License

This project is licensed under the [MIT License](LICENSE).  
Developed by [Shree](https://github.com/shree-ltc).
