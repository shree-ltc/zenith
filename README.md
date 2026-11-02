# Zenith

**High-Performance Discord Security & Server Automation Architecture**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.3+-5865F2?style=flat-square&logo=discord&logoColor=white)](https://github.com/Rapptz/discord.py)
[![License: MIT](https://img.shields.io/badge/License-MIT-success?style=flat-square)](LICENSE)
[![Discord](https://img.shields.io/badge/Discord-shree.ltc-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/users/1465912900710305822)

Zenith is an enterprise-grade, asynchronous Discord bot framework engineered for community protection, privilege escalation prevention, autonomous raid defense, and server administration. Built with `discord.py` 2.x, it integrates real-time audit log analysis, sub-millisecond memory caching, dual-engine database persistence (PostgreSQL + SQLite), and high-fidelity media streaming.

---

## Core Systems

### Mainrole Protection
* **Privilege Guard**: Protects default `@everyone` and verified member roles from receiving dangerous administrative permissions (`administrator`, `manage_roles`, `manage_channels`, `ban_members`, `kick_members`, `moderate_members`, `manage_guild`, etc.).
* **Instant Auto-Revocation**: Intercepts role permission updates on the gateway, instantly strips unauthorized dangerous permissions back to safe state, and logs the offending actor.
* **Security Audits**: Real-time auditing (`mainrole scan`) to sanitize roles currently holding dangerous permissions.

### Security & Antinuke
* **Real-Time Gateway Monitoring**: Intercepts unauthorized bans, kicks, member prunes, channel tampering, role deletion, rogue bot additions, webhooks, and guild modifications (vanity URL, name, icon).
* **Disaster Recovery & Snapshots**: Serializes complete guild structures (channels, categories, roles, permissions) to database snapshots (`antinuke snapshot`) and reconstructs damaged infrastructure automatically (`antinuke serverrecovery`).
* **Multi-Tier Authorization**: Server Owner immunity, Extra Owner registry (`extraowner`), and granular module whitelisting.

### Anti-Betray Protocol
* **Compromised Account Neutralization**: Monitors administrative action velocity in sliding time windows (e.g., 3 destructive actions in 5 seconds).
* **Autonomous Intervention**: Bypasses whitelists and immediately neutralizes rogue staff (bans or removes staff roles) if velocity thresholds are exceeded.

### Fake Permissions (Virtual Authorization)
* **Zero-Trust Moderation**: Allows guild owners to authorize staff roles to execute Zenith commands (`ban`, `kick`, `timeout`, `warn`, `lock`, `hide`, `purge`) without granting actual Discord permissions.
* **Daily Action Quotas**: Configurable per-action daily limits to strictly prevent moderator abuse or compromised account mass-bans.

### Complete Role Management Suite
* **Interactive Toggling**: Assign or strip roles on users with strict hierarchy enforcement.
* **Role Configuration**: Create, delete, rename, change color, and set hoist display.
* **Safe Mass Operations**: Rate-limited bulk assignment and removal for all members, human accounts, or bot accounts (`role all`, `role humans`, `role bots`, `rroleall`, `rrolehumans`, `rrolebots`), strictly blocking mass assignments of dangerous roles.

### Enforcement & Moderation
* **Sanctions**: Bans, softbans, kicks, timeouts, and persistent database warnings.
* **Mass Actions**: Mass unban with progress tracking (`unbanall`).
* **Channel Controls**: Lock/unlock and hide/unhide per channel or server-wide (`lockall`, `unlockall`, `hideall`, `unhideall`), and slowmode.
* **Channel Maintenance**: Clean channel nuke re-creation and channel cloning.
* **Emoji Utilities**: Steal and import custom emojis from external servers (`steal`).
* **Purge Suite**: Target-specific message purging (bots, links, users, match strings, and attachments).

### Audio & Streaming
* **Lavalink Engine**: High-fidelity audio playback with seek, volume normalization, and queue management.
* **Smart Autoplay**: Native YouTube RD mix integration and parallel artist discovery that continuously queues related tracks while filtering loops, compilations, and duplicates.
* **Interactive Controller**: Full button-driven playback control interface.

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
│   ├── logging.py         # Console formatter and rotating file logger
│   └── security.py        # Permission validators and hierarchy checks
├── ui/
│   ├── colors.py          # UI color constants
│   ├── embeds.py          # ZenithEmbed formatting helper
│   └── views.py           # Paginator and confirmation views
├── cogs/
│   ├── mainrole.py        # Protection for @everyone and verified member roles
│   ├── antinuke.py        # Anti-raid engine, snapshots, and extra owners
│   ├── antibetray.py      # Rogue staff velocity detection and neutralization
│   ├── fakepermission.py  # Virtual moderator permissions with daily quotas
│   ├── role.py            # Individual role editing and safe mass role tools
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
│   ├── music.py           # Lavalink audio streaming and autoplay
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
| **Mainrole** | `mainrole add`, `mainrole remove`, `mainrole scan`, `mainrole show` | Protects core member roles from harmful permissions. |
| **Security** | `antinuke enable`, `antinuke snapshot`, `antinuke serverrecovery`, `antinuke wl` | Real-time anti-raid protection and disaster recovery. |
| **Anti-Betray** | `antibetray enable`, `antibetray set`, `antibetray punishment` | Rogue staff velocity detection and neutralization. |
| **Fake Permissions** | `fp set`, `fp limit`, `fp limits`, `fp usage`, `fp reset` | Virtual mod permissions with daily execution quotas. |
| **Roles** | `role add`, `role remove`, `role all`, `role humans`, `role bots`, `rrole` | Individual role toggling and safe mass assignment. |
| **Moderation** | `ban`, `unban`, `softban`, `kick`, `timeout`, `warn`, `lockall`, `unbanall` | Member management and server lockdowns. |
| **Automod** | `automod antispam`, `automod antilinks`, `automod antiinvites` | Filters spam, invites, and external links. |
| **Tickets** | `ticket setup`, `ticket close`, `ticket claim`, `ticket add` | Private support channels with transcript export. |
| **Voice** | `voice lock`, `voice unlock`, `voice rename`, `voice limit` | Dynamic join-to-create temporary channels. |
| **Welcome** | `welcome channel`, `welcome message`, `autorole human` | Member greetings and initial role allocation. |
| **Economy** | `balance`, `daily`, `work`, `deposit`, `withdraw`, `pay` | Virtual currency and banking mini-games. |
| **Server** | `nuke`, `lockdown`, `unlockdown`, `dehoist`, `inrole` | Guild maintenance and administrative actions. |
| **Utility** | `userinfo`, `serverinfo`, `avatar`, `botinfo`, `ping`, `snipe` | Information lookup and diagnostics. |
| **Giveaways** | `giveaway start <duration> <winners> <prize>` | Timed community prize drawings. |
| **Music** | `play`, `skip`, `pause`, `resume`, `queue`, `autoplay`, `seek`, `volume` | Audio streaming with Lavalink and smart autoplay. |
| **AFK** | `afk [reason]` | Notifies users who mention you while away. |
| **Developer** | `reloadall`, `sync`, `eval`, `prefix` | Maintenance and hot-reloading. |

---

## Configuration Guidelines

1. **Hierarchy**: Position Zenith's role above the roles it manages in Server Settings so that moderation commands, mainrole sanitization, and role toggles succeed without hierarchy restrictions.
2. **Permissions**: Required bot permissions include `Administrator` (or `View Audit Log`, `Manage Channels`, `Manage Roles`, `Ban Members`, and `Kick Members`).
3. **Security**: Keep your `.env` file private and never commit tokens to public repositories.

---

## License

This project is licensed under the [MIT License](LICENSE).  
Developed by [Shree](https://github.com/shree-ltc).
