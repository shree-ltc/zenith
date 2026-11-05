'use client';

import React, { useEffect, useRef } from 'react';

/**
 * CyberGridPulse: Canvas-based background animation component with
 * glowing circuit pulses and interactive pointer proximity glow.
 * Built with Emil Kowalski performance restraint & 60fps canvas loop.
 */
export default function CyberGridPulse() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const mousePos = useRef({ x: -1000, y: -1000, active: false });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !canvas.parentElement) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    let width = (canvas.width = canvas.parentElement.offsetWidth);
    let height = (canvas.height = canvas.parentElement.offsetHeight);

    const onResize = () => {
      if (!canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.offsetWidth;
      height = canvas.height = canvas.parentElement.offsetHeight;
    };
    window.addEventListener('resize', onResize);

    const gridSize = 48;
    const pulses: Array<{
      x: number;
      y: number;
      isHorizontal: boolean;
      length: number;
      speed: number;
      alpha: number;
      color: string;
      progress: number;
      maxLife: number;
    }> = [];

    function spawnPulse() {
      const isHorizontal = Math.random() > 0.5;
      const x = Math.floor(Math.random() * (width / gridSize)) * gridSize;
      const y = Math.floor(Math.random() * (height / gridSize)) * gridSize;
      pulses.push({
        x,
        y,
        isHorizontal,
        length: Math.random() * 80 + 50,
        speed: (Math.random() * 1.5 + 1.2) * (Math.random() > 0.5 ? 1 : -1),
        alpha: Math.random() * 0.45 + 0.35,
        color: Math.random() > 0.3 ? '88, 101, 242' : '35, 165, 90',
        progress: 0,
        maxLife: Math.random() * 160 + 100
      });
    }

    for (let i = 0; i < 14; i++) spawnPulse();

    const onMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mousePos.current = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
        active: true
      };
    };

    const onMouseLeave = () => {
      mousePos.current.active = false;
    };

    window.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseleave', onMouseLeave);

    const render = () => {
      animId = requestAnimationFrame(render);
      ctx.clearRect(0, 0, width, height);

      // 1. Draw subtle base grid
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.025)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let x = 0; x < width; x += gridSize) {
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
      }
      for (let y = 0; y < height; y += gridSize) {
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
      }
      ctx.stroke();

      // 2. Cursor proximity illumination
      if (mousePos.current.active) {
        const radial = ctx.createRadialGradient(
          mousePos.current.x,
          mousePos.current.y,
          0,
          mousePos.current.x,
          mousePos.current.y,
          240
        );
        radial.addColorStop(0, 'rgba(88, 101, 242, 0.12)');
        radial.addColorStop(0.5, 'rgba(88, 101, 242, 0.04)');
        radial.addColorStop(1, 'rgba(88, 101, 242, 0)');
        ctx.fillStyle = radial;
        ctx.fillRect(0, 0, width, height);
      }

      // 3. Draw & update pulses
      for (let i = pulses.length - 1; i >= 0; i--) {
        const p = pulses[i];
        p.progress += Math.abs(p.speed);

        ctx.beginPath();
        if (p.isHorizontal) {
          p.x += p.speed;
          const grad = ctx.createLinearGradient(p.x, p.y, p.x + (p.speed > 0 ? p.length : -p.length), p.y);
          grad.addColorStop(0, `rgba(${p.color}, 0)`);
          grad.addColorStop(0.8, `rgba(${p.color}, ${p.alpha})`);
          grad.addColorStop(1, `rgba(${p.color}, ${p.alpha * 1.5})`);
          ctx.strokeStyle = grad;
          ctx.lineWidth = 1.5;
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(p.x + (p.speed > 0 ? p.length : -p.length), p.y);
        } else {
          p.y += p.speed;
          const grad = ctx.createLinearGradient(p.x, p.y, p.x, p.y + (p.speed > 0 ? p.length : -p.length));
          grad.addColorStop(0, `rgba(${p.color}, 0)`);
          grad.addColorStop(0.8, `rgba(${p.color}, ${p.alpha})`);
          grad.addColorStop(1, `rgba(${p.color}, ${p.alpha * 1.5})`);
          ctx.strokeStyle = grad;
          ctx.lineWidth = 1.5;
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(p.x, p.y + (p.speed > 0 ? p.length : -p.length));
        }
        ctx.stroke();

        ctx.fillStyle = `rgba(${p.color}, ${p.alpha * 1.8})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 2, 0, Math.PI * 2);
        ctx.fill();

        if (p.progress > p.maxLife || p.x < -100 || p.x > width + 100 || p.y < -100 || p.y > height + 100) {
          pulses.splice(i, 1);
          spawnPulse();
        }
      }
    };

    animId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', onResize);
      window.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseleave', onMouseLeave);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-none z-0 opacity-90"
    />
  );
}
