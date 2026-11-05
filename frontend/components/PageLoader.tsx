'use client';

import React, { useState, useEffect } from 'react';

export default function PageLoader() {
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    setProgress(35);
    const t1 = setTimeout(() => setProgress(70), 120);
    const t2 = setTimeout(() => setProgress(100), 260);
    const t3 = setTimeout(() => {
      setVisible(false);
      setTimeout(() => setProgress(0), 300);
    }, 480);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, []);

  return (
    <div
      className="fixed top-0 left-0 h-[2.5px] bg-gradient-to-r from-[#5865F2] to-[#23A55A] z-[1000000] pointer-events-none transition-all duration-300"
      style={{
        width: `${progress}%`,
        opacity: visible ? 1 : 0,
        boxShadow: '0 0 12px rgba(88, 101, 242, 0.9)'
      }}
    />
  );
}
