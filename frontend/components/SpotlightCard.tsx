'use client';

import React, { useState, useRef } from 'react';
import { motion } from 'framer-motion';

interface SpotlightCardProps {
  tag?: string;
  title?: string;
  description?: string;
  children?: React.ReactNode;
  className?: string;
}

/**
 * SpotlightCard: Cursor-tracking radial gradient border and illumination card.
 * Elevated with Framer Motion hover & active spring physics.
 */
export default function SpotlightCard({
  tag,
  title,
  description,
  children,
  className = ''
}: SpotlightCardProps) {
  const cardRef = useRef<HTMLDivElement | null>(null);
  const [mousePos, setMousePos] = useState({ x: -1000, y: -1000 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    });
  };

  return (
    <motion.div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        setMousePos({ x: -1000, y: -1000 });
      }}
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.985 }}
      transition={{ duration: 0.18, ease: [0.2, 0.8, 0.2, 1] }}
      className={`relative overflow-hidden rounded-xl border border-white/10 bg-[#12131C]/75 p-6 backdrop-blur-xl shadow-2xl ${className}`}
    >
      {/* Dynamic Cursor Spotlight Radial Overlay */}
      <div
        className="pointer-events-none absolute inset-0 transition-opacity duration-300"
        style={{
          opacity: isHovered ? 1 : 0,
          background: `radial-gradient(400px circle at ${mousePos.x}px ${mousePos.y}px, rgba(88, 101, 242, 0.16), transparent 70%)`
        }}
      />

      {/* Card Content */}
      <div className="relative z-10 flex flex-col">
        {tag && (
          <span className="self-start mb-3 rounded border border-[#5865F2]/25 bg-[#5865F2]/10 px-2.5 py-0.5 font-mono text-xs text-[#5865F2]">
            {tag}
          </span>
        )}
        {title && (
          <h3 className="mb-2 text-lg font-bold tracking-tight text-white">
            {title}
          </h3>
        )}
        {description && (
          <p className="text-sm leading-relaxed text-[#9DA3B4]">
            {description}
          </p>
        )}
        {children}
      </div>
    </motion.div>
  );
}
