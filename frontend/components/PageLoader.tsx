'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function PageLoader() {
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState(0);
  const [phaseIndex, setPhaseIndex] = useState(0);

  const phases = [
    { target: 28, phase: 'ESTABLISHING IPC GATEWAY', status: 'SYNCHRONIZING' },
    { target: 62, phase: 'VERIFYING SECURITY MATRIX', status: 'AUDIT IN-MEMORY' },
    { target: 88, phase: 'MOUNTING REACT RUNTIME', status: 'TELEMETRY LIVE' },
    { target: 100, phase: 'ALL SYSTEMS NOMINAL', status: 'SYSTEM CORE READY' }
  ];

  useEffect(() => {
    let currentStep = 0;
    const delays = [100, 150, 140, 90];

    const advance = () => {
      if (currentStep >= phases.length) {
        setTimeout(() => setLoading(false), 140);
        return;
      }

      const p = phases[currentStep];
      setProgress(p.target);
      setPhaseIndex(currentStep);

      currentStep++;
      setTimeout(advance, delays[currentStep - 1] || 100);
    };

    const timer = setTimeout(advance, 50);
    return () => clearTimeout(timer);
  }, []);

  return (
    <>
      {/* Top Slim Loading Progress Bar */}
      <div
        className="fixed top-0 left-0 h-[2px] bg-gradient-to-r from-[#5865F2] to-[#23A55A] z-[1000000] pointer-events-none transition-all duration-200"
        style={{
          width: `${progress}%`,
          opacity: loading ? 1 : 0,
          boxShadow: '0 0 10px rgba(88, 101, 242, 0.8)'
        }}
      />

      {/* Cyber Preloader Overlay */}
      <AnimatePresence>
        {loading && (
          <motion.div
            initial={{ opacity: 1 }}
            exit={{ opacity: 0, scale: 1.02, filter: 'blur(8px)' }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            className="fixed inset-0 z-[999999] flex flex-col items-center justify-center bg-[#07070A] text-white select-none pointer-events-auto"
          >
            {/* Ambient Center Glow */}
            <div className="absolute h-[320px] w-[320px] rounded-full bg-[#5865F2]/10 blur-[100px] pointer-events-none" />

            <div className="relative z-10 flex flex-col items-center max-w-xs w-full px-6">
              {/* Geometric Cut Monogram Logo */}
              <div className="relative mb-6 h-16 w-16 flex items-center justify-center">
                <div className="absolute inset-0 rounded-2xl bg-[#5865F2]/20 blur-md animate-pulse" />
                <div className="relative h-14 w-14 rounded-xl border border-white/10 bg-[#0E0F17] flex items-center justify-center font-bold text-2xl text-[#5865F2] shadow-2xl">
                  Z
                </div>
              </div>

              {/* Status Header */}
              <div className="mb-3 inline-flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-wider text-[#9DA3B4]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#23A55A] shadow-[0_0_8px_#23A55A] animate-ping" />
                <span>{phases[phaseIndex]?.status || 'INITIALIZING'}</span>
              </div>

              {/* Precision Progress Track */}
              <div className="relative mb-2 h-1 w-full overflow-hidden rounded-full bg-white/5">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-[#5865F2] to-[#23A55A] shadow-[0_0_10px_rgba(88,101,242,0.7)]"
                  style={{ width: `${progress}%` }}
                  transition={{ ease: 'easeOut', duration: 0.15 }}
                />
              </div>

              {/* Phase Meta */}
              <div className="flex w-full items-center justify-between font-mono text-[11px] text-[#5C6275]">
                <span>{phases[phaseIndex]?.phase || 'PREPARING'}</span>
                <span>{progress}%</span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
