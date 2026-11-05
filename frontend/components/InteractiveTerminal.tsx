'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface LogEntry {
  id: number;
  time: string;
  tag: string;
  type: 'ok' | 'shield' | 'warn';
  text: string;
}

export default function InteractiveTerminal() {
  const [isPaused, setIsPaused] = useState(false);
  const [activeFilter, setActiveFilter] = useState('ALL');
  const [copied, setCopied] = useState(false);
  const bodyRef = useRef<HTMLDivElement | null>(null);

  const [logs, setLogs] = useState<LogEntry[]>([
    { id: 1, time: '11:40:02', tag: '[OK]', type: 'ok', text: 'Gateway handshake verified • Session established with Discord Shard #0' },
    { id: 2, time: '11:40:04', tag: '[SHIELD]', type: 'shield', text: 'Mainrole protection audit completed • Verified 99 guilds safe from escalation' },
    { id: 3, time: '11:40:08', tag: '[OK]', type: 'ok', text: 'Antinuke audit listeners active • Intercepting bans, kicks, bot integrations & roles' },
    { id: 4, time: '11:40:12', tag: '[STORAGE]', type: 'shield', text: 'Dual engine synchronization verified • PostgreSQL + SQLite state matching' },
    { id: 5, time: '11:40:18', tag: '[NOTICE]', type: 'warn', text: 'Live Web Dashboard active on port 8080 • Direct in-memory bus synchronized' }
  ]);

  useEffect(() => {
    if (isPaused) return;

    const streamPool = [
      { tag: '[SHIELD]', type: 'shield' as const, text: 'Automod velocity checked • Rolling window clean across all monitored channels' },
      { tag: '[OK]', type: 'ok' as const, text: 'Audit cache pruned • Sub-millisecond RAM response verified' },
      { tag: '[GATEWAY]', type: 'ok' as const, text: 'Heartbeat ACK received from Discord gateway • Latency 15.2ms' },
      { tag: '[NOTICE]', type: 'warn' as const, text: 'Role hierarchy check executed • 0 dangerous privilege grants detected' },
      { tag: '[STORAGE]', type: 'shield' as const, text: 'PostgreSQL connection pool healthy • Active pool capacity: 10 connections' }
    ];

    const timer = setInterval(() => {
      const now = new Date();
      const timeStr = [now.getHours(), now.getMinutes(), now.getSeconds()]
        .map((n) => String(n).padStart(2, '0'))
        .join(':');
      const ev = streamPool[Math.floor(Math.random() * streamPool.length)];

      setLogs((prev) => {
        const next = [...prev, { id: Date.now(), time: timeStr, tag: ev.tag, type: ev.type, text: ev.text }];
        if (next.length > 30) next.shift();
        return next;
      });
    }, 4000);

    return () => clearInterval(timer);
  }, [isPaused]);

  useEffect(() => {
    if (bodyRef.current && !isPaused) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [logs, isPaused]);

  const filteredLogs = useMemo(() => {
    if (activeFilter === 'ALL') return logs;
    return logs.filter((l) => l.tag.includes(activeFilter));
  }, [logs, activeFilter]);

  const handleCopy = () => {
    const text = filteredLogs.map((l) => `[${l.time}] ${l.tag} ${l.text}`).join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="w-full overflow-hidden rounded-xl border border-white/10 bg-[#0C0D13]/90 backdrop-blur-2xl shadow-2xl">
      {/* Terminal Title Bar */}
      <div className="flex items-center justify-between border-b border-white/5 bg-[#12131B]/70 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-[#FF5F56]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#FFBD2E]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#27C93F]" />
          </div>
          <span className="font-mono text-xs text-[#9DA3B4]">
            zenith-core // real-time-telemetry-engine
          </span>
        </div>

        {/* Filter Controls */}
        <div className="flex items-center gap-2">
          {['ALL', 'SHIELD', 'OK'].map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setActiveFilter(f)}
              className={`rounded px-2 py-0.5 font-mono text-xs transition-colors ${
                activeFilter === f
                  ? 'border border-[#5865F2] bg-[#5865F2]/20 text-white'
                  : 'border border-transparent text-[#5C6275] hover:text-white'
              }`}
            >
              {f}
            </button>
          ))}

          <button
            type="button"
            onClick={() => setIsPaused(!isPaused)}
            className={`rounded border px-2 py-0.5 font-mono text-xs ${
              isPaused
                ? 'border-[#F23F43] bg-[#F23F43]/15 text-[#F23F43]'
                : 'border-[#23A55A] bg-[#23A55A]/15 text-[#23A55A]'
            }`}
          >
            {isPaused ? '[PAUSED]' : '[SYNC LIVE]'}
          </button>

          <button
            type="button"
            onClick={handleCopy}
            className="rounded border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-xs text-[#9DA3B4] hover:text-white"
          >
            {copied ? '[COPIED]' : 'COPY'}
          </button>
        </div>
      </div>

      {/* Terminal Scroll Stream */}
      <div
        ref={bodyRef}
        className="max-h-56 overflow-y-auto p-4 font-mono text-xs leading-relaxed text-[#D1D5DB]"
      >
        <AnimatePresence initial={false}>
          {filteredLogs.map((log) => (
            <motion.div
              key={log.id}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className="mb-1"
            >
              <span className="text-[#5C6275]">[{log.time}] </span>
              <span
                className={
                  log.type === 'ok'
                    ? 'text-[#23A55A] font-semibold'
                    : log.type === 'shield'
                    ? 'text-[#5865F2] font-semibold'
                    : 'text-[#F0B232] font-semibold'
                }
              >
                {log.tag}{' '}
              </span>
              <span>{log.text}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
