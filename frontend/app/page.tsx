'use client';

import React from 'react';
import PageLoader from '@/components/PageLoader';
import CyberGridPulse from '@/components/CyberGridPulse';
import SpotlightCard from '@/components/SpotlightCard';
import InteractiveTerminal from '@/components/InteractiveTerminal';
import InteractivePipeline from '@/components/InteractivePipeline';
import CommandMatrix from '@/components/CommandMatrix';

export default function Home() {
  return (
    <main className="relative min-h-screen w-full bg-[#07070A] text-white">
      {/* Precision Boot Loader & Top Loading Bar */}
      <PageLoader />

      {/* Background Interactive Cyber Grid Canvas */}
      <div className="absolute inset-0 h-[640px] overflow-hidden pointer-events-none">
        <CyberGridPulse />
      </div>

      {/* Symmetrical Navbar */}
      <header className="sticky top-0 z-50 w-full border-b border-white/10 bg-[#09090D]/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg border border-white/10 bg-white/5 p-1 flex items-center justify-center font-bold text-[#5865F2]">
              Z
            </div>
            <span className="font-bold text-lg">Zenith</span>
            <span className="rounded bg-[#5865F2]/10 px-2 py-0.5 font-mono text-xs text-[#5865F2] border border-[#5865F2]/20">
              v1.0.0
            </span>
          </div>

          <div className="flex items-center gap-4">
            <span className="hidden md:inline-flex items-center gap-2 rounded-full border border-[#23A55A]/30 bg-[#23A55A]/10 px-3 py-1 font-mono text-xs text-[#23A55A]">
              <span className="h-2 w-2 rounded-full bg-[#23A55A] animate-pulse" />
              GATEWAY ONLINE
            </span>
            <a
              href="https://discord.com/oauth2/authorize?client_id=1465912900710305822&permissions=8&scope=bot%20applications.commands"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-md bg-[#5865F2] px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-[#5865F2]/25 hover:bg-[#6875F5] active:scale-95 transition-all"
            >
              Add to Discord
            </a>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative z-10 mx-auto max-w-5xl px-6 pt-20 pb-12 text-center">
        <span className="inline-block rounded-full border border-[#5865F2]/25 bg-[#5865F2]/10 px-4 py-1 font-mono text-xs text-[#5865F2] mb-6">
          ENTERPRISE DISCORD DEFENSE ARCHITECTURE
        </span>

        <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight text-white mb-6">
          High-Performance Discord Security<br />
          <span className="bg-gradient-to-r from-white via-white/90 to-[#9DA3B4] bg-clip-text text-transparent">
            & Autonomous Administration
          </span>
        </h1>

        <p className="mx-auto max-w-2xl text-base md:text-lg text-[#9DA3B4] mb-10 leading-relaxed">
          Engineered for community defense, privilege escalation prevention, autonomous raid neutralization,
          and complete server orchestration with 504 direct command endpoints.
        </p>

        {/* Real-Time Interactive Telemetry Terminal Component */}
        <InteractiveTerminal />
      </section>

      {/* Core Defense Systems (Spotlight Cards Grid) */}
      <section className="mx-auto max-w-7xl px-6 py-12">
        <div className="text-center mb-12">
          <span className="font-mono text-xs text-[#5865F2] uppercase tracking-wider">
            [DEFENSE ARCHITECTURE]
          </span>
          <h2 className="text-3xl font-extrabold text-white mt-1">
            Built For Extreme Reliability
          </h2>
          <p className="text-sm text-[#9DA3B4] mt-2">
            Zero privilege leaks, zero decorative clutter, and autonomous real-time protection.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <SpotlightCard
            tag="[SECURITY] MAINROLE GUARD"
            title="Privilege Escalation Shield"
            description="Guards default @everyone and verified member roles from receiving dangerous administrative permissions. Strips illegal grants in under 0.5s."
          />
          <SpotlightCard
            tag="[ANTINUKE] GATEWAY DEFENSE"
            title="Autonomous Raid Defense"
            description="Monitors audit logs for unauthorized channel deletions, role tampering, and rogue bot additions. Instantly neutralizes offending actors."
          />
          <SpotlightCard
            tag="[VELOCITY] ANTI-BETRAY SHIELD"
            title="Compromised Staff Mitigation"
            description="Tracks moderator velocity in rolling time windows. When actions exceed safety thresholds, the actor is quarantined instantly."
          />
          <SpotlightCard
            tag="[MODERATION] FAKE PERMISSIONS"
            title="Zero-Trust Staff Authorization"
            description="Grants Zenith moderation authority to staff roles without assigning native Discord permissions, guarded by daily action quotas."
          />
          <SpotlightCard
            tag="[PURIFICATION] PURGE MATRIX"
            title="Target-Specific Message Purge"
            description="15 dedicated purification commands designed for clean message sweeps: bots, links, embeds, attachments, and specific users."
          />
          <SpotlightCard
            tag="[STREAMING] AUDIO ENGINE"
            title="Lavalink & Smart Autoplay"
            description="High-fidelity audio streaming integrated with YouTube RD Mix and parallel artist discovery that continuously queues related tracks."
          />
        </div>
      </section>

      {/* Interactive Command Matrix */}
      <section className="mx-auto max-w-7xl px-6 py-12">
        <div className="text-center mb-10">
          <span className="font-mono text-xs text-[#5865F2] uppercase tracking-wider">
            [COMMAND MATRIX]
          </span>
          <h2 className="text-3xl font-extrabold text-white mt-1">
            504 Direct Endpoints • 816 Invocable Triggers
          </h2>
        </div>
        <CommandMatrix />
      </section>

      {/* Interactive Three-Tier Defense Pipeline */}
      <section className="mx-auto max-w-7xl px-6 py-12">
        <div className="text-center mb-10">
          <span className="font-mono text-xs text-[#5865F2] uppercase tracking-wider">
            [SYSTEM ARCHITECTURE]
          </span>
          <h2 className="text-3xl font-extrabold text-white mt-1">
            Three-Tier Defense Pipeline
          </h2>
        </div>
        <InteractivePipeline />
      </section>

      {/* Footer */}
      <footer className="border-t border-white/10 bg-[#09090D] py-10 text-center text-xs text-[#5C6275]">
        <p>Engineered by <a href="https://github.com/shree-ltc" className="text-[#5865F2] underline font-semibold">Shree</a> • Open-Source MIT License</p>
        <p className="mt-2 font-mono text-[11px]">Discord: shree.ltc (ID: 1465912900710305822) • Zero Decorative Emojis • Sub-millisecond Execution Bus</p>
      </footer>
    </main>
  );
}
