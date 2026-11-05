<div align="center">
  <img src="assets/logo.svg" width="128" height="128" alt="Zenith Logo" />
  <h1>Zenith</h1>
  <p><b>High-Performance Discord Security &amp; Server Automation Architecture</b></p>

  <p>
    <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+" /></a>
    <a href="https://github.com/Rapptz/discord.py"><img src="https://img.shields.io/badge/Components_V2-Enabled-000000?style=flat-square&logo=discord&logoColor=white" alt="Components V2" /></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-success?style=flat-square" alt="License: MIT" /></a>
    <a href="https://discord.com/users/1465912900710305822"><img src="https://img.shields.io/badge/Discord-shree.ltc-5865F2?style=flat-square&logo=discord&logoColor=white" alt="Discord" /></a>
  </p>
</div>

Zenith is an enterprise-grade, asynchronous Discord bot framework engineered for community protection, privilege escalation prevention, autonomous raid defense, and server administration. Built on `discord.py` 2.x and integrated with an **embedded zero-latency Web Dashboard & Control Plane** (`aiohttp`), it features real-time audit log analysis, sub-millisecond memory caching, dual-engine database persistence (PostgreSQL + SQLite), and high-fidelity media streaming.

Zenith is equipped with **47 distinct feature modules**, providing **504 direct command endpoints** and **816 total invocable triggers** with a unified obsidian theme (`0x0F0F13`).

---

## Core Systems & Highlights

### Discord Components V2 Architecture
* **Pure Obsidian Styling (`0x000000`)**: Full implementation of Discord's next-generation Components V2 layout (`Container`, `Section`, `TextDisplay`, `Separator`, `ActionRow`, `Thumbnail`).
* **Nested Interactive Controls**: All interactive controls (buttons, pagination switches, confirmation toggles, category dropdown selects) are cleanly nested **INSIDE** the Container via `ActionRow`.
* **Universal Conversion Layer**: Zenith's custom execution context (`ZenithContext`) automatically adapts standard Discord responses and embeds into sleek obsidian Components V2 Containers, guaranteeing uniform visual presentation across all 504 command endpoints.
* **Interactive Help & Diagnostics**: Category explorer, telemetry latency displays, and multi-page statistics views built directly on Components V2.

### Integrated Web Dashboard & Control Plane
* **Embedded Zero-Latency Web Server**: Runs directly inside Zenith's event loop on port `8080` with direct in-memory access to active guilds, channels, roles, and database states.
* **Modern Obsidian Control Panel (`/dashboard`)**:
  * Real-time gateway ping counter and live server diagnostic health.
  * Antinuke & raid defense master switch and module toggles (anti-ban, anti-kick, anti-bot, anti-role, etc.).
  * Automod filter matrix and interactive forbidden word chip registry.
  * Welcome onboarding editor with dynamic variable live preview (`{user}`, `{server}`, `{count}`).
  * Mainrole privilege audit runner and instant role sanitizer.
  * Emergency Panic button for one-click channel lockdowns.
* **Official Landing Website (`/`)**: Minimalist black 'Z' branding, live telemetry counters, and system highlights.

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

### Enterprise Automod
* Granular filters for spam bursts, discord invites, external links, excessive capitalization, mass user mentions, emoji flooding, zalgo/corrupted text, dangerous file attachments, excessive newlines, and character length limits.
* Whitelist overrides for trusted roles and channels, custom forbidden word matching, and centralized logging.

### Purification Suite (Purge Engine)
* High-velocity bulk cleanup with target-specific purges: `clearall`, `clearuser`, `clearbots`, `clearembeds`, `clearmentions`, `clearreactions`, `clearfiles`, `clearimages`, `clearemojis`, `clearcontains`, `clearinvites`, `clearlinks`, `clearwebhooks`, and `clearuntil`.

### Complete Role Management Suite
* Interactive role toggling, creation, renaming, color adjustment, hoist configuration, permission inspections, and role duplication.
* Safe mass operations: Rate-limited bulk assignment and removal for all members, human accounts, or bot accounts (`role all`, `role humans`, `role bots`, `rrole all`, `rrole humans`, `rrole bots`).

### Audio & Streaming
* **Lavalink Engine**: High-fidelity audio playback with seek, volume normalization, and queue management.
* **Smart Autoplay**: Native YouTube RD mix integration and parallel artist discovery that continuously queues related tracks while filtering loops, compilations, and duplicates.
* **Interactive Controller**: Full button-driven playback control interface.

---

## Installation & Setup

### Prerequisites
* Python 3.10+
* Discord Bot Token with all Privileged Gateway Intents enabled (Message Content, Server Members, Presence) in the Discord Developer Portal.
* Optional: Redis instance for high-throughput caching and PostgreSQL for multi-sharded deployments (defaults to local SQLite and memory cache).

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

## Command Reference (504 Endpoints, 816 Triggers)

| Category | Endpoints | Example Triggers | Description |
| :--- | :--- | :--- | :--- |
| **Mainrole** | 5 | `mainrole add`, `mainrole remove`, `mainrole scan`, `mainrole show` | Protects core member roles from dangerous permissions. |
| **Antinuke** | 20 | `antinuke enable`, `antinuke snapshot`, `antinuke serverrecovery`, `extraowner add` | Real-time anti-raid protection, snapshots, and recovery. |
| **Anti-Betray** | 8 | `antibetray enable`, `antibetray threshold`, `antibetray punishment` | Rogue staff velocity detection and neutralization. |
| **Fake Permissions**| 9 | `fp set`, `fp limit`, `fp limits`, `fp usage`, `fp reset` | Virtual mod permissions with daily quotas. |
| **Automod** | 18 | `automod antispam`, `automod antilinks`, `automod words add` | Granular regex message scanner and burst limiter. |
| **Moderation** | 22 | `ban`, `unban`, `softban`, `kick`, `timeout`, `warn`, `lockall`, `unbanall` | Sanctions, member management, and channel lockdowns. |
| **Purge Engine** | 15 | `clear`, `clearuser`, `clearbots`, `clearembeds`, `clearlinks` | Target-specific high-velocity message purification. |
| **Cases & Logs** | 11 | `case edit`, `case reason`, `case search`, `modlogs`, `banlist` | Persistent moderation action tracking and audit logging. |
| **Roles** | 22 | `role add`, `role create`, `role all`, `role humans`, `rrole all` | Individual role management and bulk safe operations. |
| **Tags** | 13 | `tag get`, `tag add`, `tag edit`, `tag raw`, `tag claim`, `tag alias` | Guild-scoped custom tags and snippet engine. |
| **Highlights** | 4 | `highlight add`, `highlight remove`, `highlight list`, `highlight clear` | Personal keyword alerts with DM notifications. |
| **Tickets** | 10 | `ticket setup`, `ticket close`, `ticket claim`, `ticket transcript` | Private support channels with transcript export. |
| **Voice** | 15 | `voice setup`, `voice lock`, `voice rename`, `voice permit`, `voice limit` | Dynamic join-to-create temporary voice lounges. |
| **Voice Activity**| 3 | `voiceactivity`, `voicetop`, `voicereset` | Automatic tracking of member voice time and leaderboards. |
| **Music** | 14 | `play`, `skip`, `pause`, `queue`, `autoplay`, `volume`, `seek` | High-fidelity audio streaming and smart YouTube autoplay. |
| **Economy** | 19 | `balance`, `daily`, `work`, `crime`, `rob`, `deposit`, `shop`, `slots` | Virtual currency, commerce, inventory, and mini-games. |
| **Leveling** | 11 | `rank`, `levels`, `leveling channel`, `rewards add`, `setlevel` | Progression tracking, tiered role rewards, and leaderboards. |
| **Giveaways** | 14 | `giveaway start`, `giveaway drop`, `giveaway reroll`, `gstart` | Timed community prize drawings with button entries. |
| **Suggestions** | 9 | `suggest`, `suggestion channel`, `accept`, `deny`, `consider` | Community feedback lifecycle with voting and comments. |
| **Starboard** | 9 | `starboard channel`, `threshold`, `selfstar`, `starboard emoji` | Message showcase engine with customizable threshold. |
| **Sticky Messages**| 7 | `sticky add`, `sticky remove`, `sticky list`, `sticky edit` | Persistent message broadcaster pinned at bottom of channels. |
| **Birthdays** | 9 | `birthday set`, `birthday upcoming`, `birthday channel`, `birthday role` | Automated member celebration engine and announcements. |
| **Games** | 8 | `tictactoe`, `blackjack`, `guessnumber`, `connectfour`, `trivia` | Turn-based challenges, board games, and typing races. |
| **Text Tools** | 17 | `mock`, `reverse`, `vaporwave`, `binary`, `morse`, `base64`, `rot13` | Ciphers, text transformations, hashing, and formatting. |
| **Utility** | 16 | `userinfo`, `serverinfo`, `avatar`, `calc`, `snipe`, `editsnipe` | Diagnostics, mathematical calculations, and inspections. |
| **Lookup** | 8 | `useravatar`, `serverbanner`, `servericon`, `membercount`, `roleinfo` | Dedicated asset lookup and permissions matrix. |
| **Activity Tracker**| 8 | `invites`, `topinvites`, `messages`, `topmessages`, `invitebonus` | Gateway message count and invite link tracking. |
| **Server Counters** | 6 | `stats channel`, `stats category`, `stats format`, `stats refresh` | Dynamic voice/text statistics counters in channel list. |
| **Profiles** | 9 | `profile`, `setbio`, `rep`, `marry`, `divorce`, `badges`, `reptop` | Social profiles, user biographies, and relationships. |
| **AFK Engine** | 3 | `afk`, `afklist`, `afkclear` | Away status broadcasting and mention alerts. |
| **Welcome & Leave**| 6 | `welcome channel`, `welcome message`, `leave channel`, `welcome test` | Custom arrival/departure messages and cards. |
| **Autoroles** | 8 | `autorole humans add`, `autorole bots add`, `autorole show` | Automated join role allocation for humans and bots. |
| **Reaction Roles** | 7 | `reactionrole add`, `reactionrole remove`, `reactionrole create` | Self-service role selection panels. |
| **Autoresponder** | 6 | `autoresponder add`, `autoresponder remove`, `autoresponder list` | Trigger-based automated message responses. |
| **Autoreact** | 7 | `autoreact add`, `autoreact list`, `autoreact channel add` | Automated reaction triggers per keyword or channel. |
| **Ignore Engine** | 10 | `ignore channel`, `ignore command`, `ignore user`, `ignore bypass` | Granular permission blacklisting and bypass rules. |
| **No-Prefix** | 4 | `noprefix add`, `noprefix remove`, `noprefix list`, `noprefix clear` | Global prefix bypass authorization for VIPs and staff. |
| **Embed Builder** | 5 | `embed create`, `embed json`, `embed say`, `embed edit` | Interactive custom embed generation and dispatch. |
| **Audit Logs** | 7 | `modlog`, `serverlog`, `messagelog`, `memberlog`, `voicelog` | Comprehensive guild event auditing. |
| **General** | 6 | `remind`, `remind list`, `timestamp`, `worldclock`, `uptime` | Productivity reminders and timezone calculations. |
| **Telemetry** | 5 | `latency`, `statsbot`, `shards`, `memory`, `system` | Bot performance, process memory, and host telemetry. |
| **Mention Reply** | 4 | `mention_reply toggle`, `mention_reply message` | Customizable response when the bot is pinged. |
| **Dashboard** | 1 | `dashboard`, `web`, `panel` | Displays access links to the integrated real-time web control plane. |
| **Administration** | 11 | `eval`, `reloadall`, `sync`, `prefix`, `blacklist`, `maintenance` | Host maintenance, slash sync, and hot code reloading. |
| **Help Engine** | 2 | `help`, `help <command>` | Interactive 25-option category menu and command inspector. |

---

## Configuration Guidelines

1. **Hierarchy Placement**: Position Zenith's role above all roles it manages in Server Settings so that moderation commands, mainrole sanitization, and role assignment execute without hierarchy violations.
2. **Permissions**: Required bot permissions include `Administrator` (or `View Audit Log`, `Manage Channels`, `Manage Roles`, `Ban Members`, and `Kick Members`).
3. **Security**: Keep your `.env` file private and never commit tokens to public repositories.

---

## License

This project is licensed under the [MIT License](LICENSE).  
Engineered by [Shree](https://github.com/shree-ltc).
