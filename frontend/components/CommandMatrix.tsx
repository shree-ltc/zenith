'use client';

import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';

export default function CommandMatrix() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [copiedTrigger, setCopiedTrigger] = useState<string | null>(null);

  const commandsData = [
    { trigger: 'mainrole scan', category: 'security', perms: 'Server Owner', desc: 'Audits all protected roles and strips active dangerous permissions.' },
    { trigger: 'antinuke enable', category: 'security', perms: 'Server Owner', desc: 'Arms real-time audit log interceptor against unauthorized attacks.' },
    { trigger: 'antinuke snapshot', category: 'security', perms: 'Server Owner', desc: 'Serializes complete guild structure, roles, and channels to database.' },
    { trigger: 'antibetray set <count> <sec>', category: 'security', perms: 'Server Owner', desc: 'Configures velocity limit for staff administrative actions.' },
    { trigger: 'fp set <@role>', category: 'security', perms: 'Server Owner', desc: 'Authorizes a staff role to run Zenith moderation without Discord perms.' },
    { trigger: 'ban <@user> [reason]', category: 'moderation', perms: 'Ban Members', desc: 'Bans a member with strict hierarchy & Server Owner protection checks.' },
    { trigger: 'clearall [amount]', category: 'moderation', perms: 'Manage Messages', desc: 'Purges up to 100 messages with high-speed rate-limited cleanup.' },
    { trigger: 'clearlinks [amount]', category: 'moderation', perms: 'Manage Messages', desc: 'Purges only messages containing external links or invites.' },
    { trigger: 'voice setup', category: 'voice', perms: 'Manage Channels', desc: 'Creates automated Join-to-Create temporary voice lounge system.' },
    { trigger: 'voice lock', category: 'voice', perms: 'Voice Owner', desc: 'Locks current temporary voice channel to prevent unwanted joins.' },
    { trigger: 'automod antispam <on/off>', category: 'automod', perms: 'Administrator', desc: 'Enforces burst rate-limits on incoming channel messages.' },
    { trigger: 'automod words add <word>', category: 'automod', perms: 'Administrator', desc: 'Adds forbidden term to real-time message suppression engine.' },
    { trigger: 'play <query / url>', category: 'music', perms: 'Connect', desc: 'High-fidelity audio streaming through Lavalink cluster.' },
    { trigger: 'autoplay', category: 'music', perms: 'Connect', desc: 'Toggles intelligent YouTube RD mix parallel track discovery.' }
  ];

  const categories = [
    { id: 'all', label: 'All Modules' },
    { id: 'security', label: 'Security & Antinuke' },
    { id: 'moderation', label: 'Moderation & Purge' },
    { id: 'voice', label: 'Voice & Lounges' },
    { id: 'automod', label: 'Automod Matrix' },
    { id: 'music', label: 'Audio & Lavalink' }
  ];

  const filtered = useMemo(() => {
    return commandsData.filter((c) => {
      const matchesCat = category === 'all' || c.category === category;
      const matchesSearch =
        c.trigger.toLowerCase().includes(search.toLowerCase()) ||
        c.desc.toLowerCase().includes(search.toLowerCase()) ||
        c.perms.toLowerCase().includes(search.toLowerCase());
      return matchesCat && matchesSearch;
    });
  }, [category, search]);

  const handleCopy = (trigger: string) => {
    navigator.clipboard.writeText(`z!${trigger}`);
    setCopiedTrigger(trigger);
    setTimeout(() => setCopiedTrigger(null), 1800);
  };

  return (
    <div className="w-full rounded-xl border border-white/10 bg-[#12131C]/75 p-6 backdrop-blur-xl shadow-2xl mb-16">
      {/* Search Input */}
      <div className="mb-5">
        <input
          type="text"
          placeholder="Filter 504 commands by trigger, permission, or description..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-md border border-white/10 bg-[#13141D]/90 px-4 py-2 text-sm text-white placeholder-[#5C6275] focus:border-[#5865F2] focus:outline-none focus:ring-2 focus:ring-[#5865F2]/25"
        />
      </div>

      {/* Categories */}
      <div className="flex flex-wrap gap-2 mb-6">
        {categories.map((cat) => (
          <button
            key={cat.id}
            type="button"
            onClick={() => setCategory(cat.id)}
            className={`rounded-full px-3.5 py-1.5 font-mono text-xs transition-colors ${
              category === cat.id
                ? 'border border-[#5865F2] bg-[#5865F2]/20 text-white shadow-[0_0_12px_rgba(88,101,242,0.35)]'
                : 'border border-white/10 bg-[#13141D] text-[#9DA3B4] hover:text-white'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-white/10 font-mono text-xs uppercase text-[#5C6275]">
            <tr>
              <th className="pb-3 pr-4">Primary Trigger</th>
              <th className="pb-3 pr-4">Permission Level</th>
              <th className="pb-3 pr-4">Description</th>
              <th className="pb-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {filtered.map((c) => (
              <tr key={c.trigger} className="hover:bg-white/[0.02] transition-colors">
                <td className="py-3 pr-4 font-mono font-semibold text-[#5865F2]">
                  z!{c.trigger}
                </td>
                <td className="py-3 pr-4 font-mono text-xs text-[#9DA3B4]">
                  {c.perms}
                </td>
                <td className="py-3 pr-4 text-[#9DA3B4]">{c.desc}</td>
                <td className="py-3 text-right">
                  <button
                    type="button"
                    onClick={() => handleCopy(c.trigger)}
                    className="rounded border border-white/10 bg-white/5 px-2.5 py-1 font-mono text-xs text-[#9DA3B4] hover:bg-white/10 hover:text-white"
                  >
                    {copiedTrigger === c.trigger ? '[OK]' : 'Copy'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
