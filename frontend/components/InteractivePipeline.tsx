'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';

export default function InteractivePipeline() {
  const [selectedStage, setSelectedStage] = useState(0);

  const stages = [
    {
      num: '01',
      title: 'Gateway Interception',
      desc: 'Intercepts incoming guild events and permission grants before members are exposed to unauthorized privilege escalations.',
      specs: ['Latency: < 0.2ms', 'Interceptor: Async Hook', 'Coverage: 100% Events']
    },
    {
      num: '02',
      title: 'In-Memory Security Shield',
      desc: 'Validates actor hierarchy, whitelists, and daily quota consumption with sub-millisecond RAM response.',
      specs: ['Cache: Redis + RAM', 'Evaluation: O(1) Lookup', 'Quotas: Rolling Windows']
    },
    {
      num: '03',
      title: 'Dual-Engine Persistence',
      desc: 'Reconstructs damaged channels and role hierarchies from serialized snapshots across PostgreSQL and SQLite.',
      specs: ['Sync: Bi-directional', 'Snapshots: Instant Rollback', 'Integrity: Crypto Hash']
    }
  ];

  return (
    <div className="w-full mb-16">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-5">
        {stages.map((st, idx) => (
          <motion.div
            key={st.num}
            onClick={() => setSelectedStage(idx)}
            whileHover={{ y: -2 }}
            whileTap={{ scale: 0.985 }}
            className={`cursor-pointer rounded-xl border p-6 backdrop-blur-xl transition-colors ${
              selectedStage === idx
                ? 'border-[#5865F2] bg-[#5865F2]/10 shadow-[0_12px_30px_rgba(88,101,242,0.3)]'
                : 'border-white/10 bg-[#12131C]/70 shadow-xl hover:border-white/20'
            }`}
          >
            <div className="mx-auto mb-4 flex h-9 w-9 items-center justify-center rounded-full border border-[#5865F2]/30 bg-[#5865F2]/15 font-mono text-xs text-[#5865F2]">
              {st.num}
            </div>
            <h3 className="mb-2 text-center text-base font-bold text-white">
              {st.title}
            </h3>
            <p className="text-center text-xs leading-relaxed text-[#9DA3B4]">
              {st.desc}
            </p>
          </motion.div>
        ))}
      </div>

      {/* Inspector Details */}
      <motion.div
        key={selectedStage}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="rounded-xl border border-white/10 bg-[#0E0F17]/90 p-5 shadow-2xl"
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <span className="font-mono text-xs text-[#5865F2]">
              STAGE {stages[selectedStage].num} // ACTIVE DIAGNOSTIC TELEMETRY
            </span>
            <h4 className="mt-1 text-lg font-bold text-white">
              {stages[selectedStage].title}
            </h4>
          </div>

          <div className="flex flex-wrap gap-2">
            {stages[selectedStage].specs.map((sp) => (
              <span
                key={sp}
                className="rounded border border-white/10 bg-white/5 px-3 py-1 font-mono text-xs text-[#9DA3B4]"
              >
                {sp}
              </span>
            ))}
          </div>
        </div>
      </motion.div>
    </div>
  );
}
