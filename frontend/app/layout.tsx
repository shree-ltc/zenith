import React from 'react';
import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Zenith • Enterprise Discord Security & Automation Architecture',
  description: 'High-Performance Discord Security & Autonomous Administration engineered by Shree.',
  icons: {
    icon: '/favicon.svg'
  }
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-type="software" data-motion="true" className="dark">
      <body className="bg-[#07070A] text-white antialiased overflow-x-hidden selection:bg-[#5865F2]/30 selection:text-white">
        {children}
      </body>
    </html>
  );
}
