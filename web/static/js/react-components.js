/**
 * Zenith Enterprise React Animation Effect Components
 * Engineered by Shree (Discord ID: 1465912900710305822 | github.com/shree-ltc)
 * Standards: Taste Skill 2.5 (anti-slop) & Motion Design Principles (Emil Kowalski, Jakub Krehel)
 * Zero Decorative Emojis • Sub-millisecond Execution Bus
 */

(function () {
  const { useState, useEffect, useRef, useMemo } = React;

  // =========================================================================
  // 1. CyberGridPulse: Interactive Canvas Background Effect Component
  // =========================================================================
  function CyberGridPulse() {
    const canvasRef = useRef(null);
    const mousePos = useRef({ x: -1000, y: -1000, active: false });

    useEffect(() => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      let animationFrameId;
      let width = (canvas.width = canvas.parentElement.offsetWidth);
      let height = (canvas.height = canvas.parentElement.offsetHeight);

      const handleResize = () => {
        if (!canvas.parentElement) return;
        width = canvas.width = canvas.parentElement.offsetWidth;
        height = canvas.height = canvas.parentElement.offsetHeight;
      };
      window.addEventListener('resize', handleResize);

      // Grid signals traveling along circuit paths
      const gridSize = 48;
      const pulses = [];
      const maxPulses = 14;

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
          color: Math.random() > 0.3 ? '88, 101, 242' : '35, 165, 90', // Accent blue or green
          progress: 0,
          maxLife: Math.random() * 160 + 100
        });
      }

      for (let i = 0; i < maxPulses; i++) spawnPulse();

      const handleMouseMove = (e) => {
        const rect = canvas.getBoundingClientRect();
        mousePos.current = {
          x: e.clientX - rect.left,
          y: e.clientY - rect.top,
          active: true
        };
      };

      const handleMouseLeave = () => {
        mousePos.current.active = false;
      };

      window.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseleave', handleMouseLeave);

      let lastTime = performance.now();
      const render = (time) => {
        animationFrameId = requestAnimationFrame(render);
        const delta = Math.min((time - lastTime) / 1000, 0.1);
        lastTime = time;

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

        // 2. Interactive cursor proximity illumination
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

          // Particle beacon node at head
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

      animationFrameId = requestAnimationFrame(render);

      return () => {
        cancelAnimationFrame(animationFrameId);
        window.removeEventListener('resize', handleResize);
        window.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseleave', handleMouseLeave);
      };
    }, []);

    return React.createElement('canvas', {
      ref: canvasRef,
      style: {
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 0,
        opacity: 0.95
      }
    });
  }

  // =========================================================================
  // 2. SpotlightCard: React Cursor-Spotlight Animated Card Component
  // =========================================================================
  function SpotlightCard({ tag, title, description, children, className = '' }) {
    const cardRef = useRef(null);
    const [mousePos, setMousePos] = useState({ x: -1000, y: -1000 });
    const [isHovered, setIsHovered] = useState(false);

    const handleMouseMove = (e) => {
      if (!cardRef.current) return;
      const rect = cardRef.current.getBoundingClientRect();
      setMousePos({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top
      });
    };

    return React.createElement(
      'div',
      {
        ref: cardRef,
        className: `glass-card spotlight-card ${className}`,
        onMouseMove: handleMouseMove,
        onMouseEnter: () => setIsHovered(true),
        onMouseLeave: () => {
          setIsHovered(false);
          setMousePos({ x: -1000, y: -1000 });
        },
        style: {
          position: 'relative',
          overflow: 'hidden',
          transition: 'transform var(--m-out) var(--m-ease), border-color var(--m-out) var(--m-ease), box-shadow var(--m-out) var(--m-ease)'
        }
      },
      // Radial Spotlight Overlay
      React.createElement('div', {
        style: {
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          pointerEvents: 'none',
          opacity: isHovered ? 1 : 0,
          transition: 'opacity 0.25s var(--m-ease)',
          background: `radial-gradient(380px circle at ${mousePos.x}px ${mousePos.y}px, rgba(88, 101, 242, 0.16), transparent 70%)`,
          zIndex: 0
        }
      }),
      // Content wrapper
      React.createElement(
        'div',
        { style: { position: 'relative', zIndex: 1 } },
        tag && React.createElement('span', { className: 'feature-tag' }, tag),
        title && React.createElement('h3', { className: 'feature-title' }, title),
        description && React.createElement('p', { className: 'feature-desc' }, description),
        children
      )
    );
  }

  // =========================================================================
  // 3. AnimatedCounter: Spring Digit Roll Component
  // =========================================================================
  function AnimatedCounter({ value, suffix = '', duration = 1200 }) {
    const [displayValue, setDisplayValue] = useState(0);

    useEffect(() => {
      const numValue = typeof value === 'number' ? value : parseInt(value, 10);
      if (isNaN(numValue)) {
        setDisplayValue(value);
        return;
      }

      let startTime = null;
      let animId;

      const step = (timestamp) => {
        if (!startTime) startTime = timestamp;
        const elapsed = timestamp - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Ease out expo: 1 - Math.pow(2, -10 * progress)
        const easeProgress = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
        const current = Math.floor(easeProgress * numValue);
        setDisplayValue(current);

        if (progress < 1) {
          animId = requestAnimationFrame(step);
        } else {
          setDisplayValue(numValue);
        }
      };

      animId = requestAnimationFrame(step);
      return () => cancelAnimationFrame(animId);
    }, [value, duration]);

    return React.createElement(
      'span',
      null,
      typeof displayValue === 'number' ? displayValue.toLocaleString() : displayValue,
      suffix
    );
  }

  // =========================================================================
  // 4. InteractiveTelemetryTerminal: Real-Time Stream Component
  // =========================================================================
  function InteractiveTelemetryTerminal() {
    const [isPaused, setIsPaused] = useState(false);
    const [copied, setCopied] = useState(false);
    const bodyRef = useRef(null);

    const [logs, setLogs] = useState([
      { id: 1, time: '11:40:02', tag: '[OK]', type: 'ok', text: 'Gateway handshake verified • Session established with Discord Shard #0' },
      { id: 2, time: '11:40:04', tag: '[SHIELD]', type: 'shield', text: 'Mainrole protection audit completed • Verified 99 guilds safe from escalation' },
      { id: 3, time: '11:40:08', tag: '[OK]', type: 'ok', text: 'Antinuke audit listeners active • Intercepting bans, kicks, bot integrations & roles' },
      { id: 4, time: '11:40:12', tag: '[STORAGE]', type: 'shield', text: 'Dual engine synchronization verified • PostgreSQL + SQLite state matching' },
      { id: 5, time: '11:40:18', tag: '[NOTICE]', type: 'warn', text: 'Live Web Dashboard active on port 8080 • Direct in-memory bus synchronized' }
    ]);

    // Live stream simulation when unpaused
    useEffect(() => {
      if (isPaused) return;

      const randomEvents = [
        { tag: '[SHIELD]', type: 'shield', text: 'Automod velocity checked • Rolling window clean across all monitored channels' },
        { tag: '[OK]', type: 'ok', text: 'Audit cache pruned • Sub-millisecond RAM response verified' },
        { tag: '[GATEWAY]', type: 'ok', text: 'Heartbeat ACK received from Discord gateway • Latency 15.2ms' },
        { tag: '[NOTICE]', type: 'warn', text: 'Role hierarchy check executed • 0 dangerous privilege grants detected' },
        { tag: '[STORAGE]', type: 'shield', text: 'PostgreSQL connection pool healthy • Active pool capacity: 10 connections' }
      ];

      const interval = setInterval(() => {
        const now = new Date();
        const timeStr = [now.getHours(), now.getMinutes(), now.getSeconds()]
          .map((n) => String(n).padStart(2, '0'))
          .join(':');
        const ev = randomEvents[Math.floor(Math.random() * randomEvents.length)];

        setLogs((prev) => {
          const next = [...prev, { id: Date.now(), time: timeStr, tag: ev.tag, type: ev.type, text: ev.text }];
          if (next.length > 25) next.shift();
          return next;
        });
      }, 3600);

      return () => clearInterval(interval);
    }, [isPaused]);

    // Auto-scroll to bottom
    useEffect(() => {
      if (bodyRef.current && !isPaused) {
        bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
      }
    }, [logs, isPaused]);

    const handleCopy = () => {
      const text = logs.map((l) => `[${l.time}] ${l.tag} ${l.text}`).join('\n');
      navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    };

    return React.createElement(
      'div',
      { className: 'terminal-window', style: { width: '100%', marginBottom: '4.5rem' } },
      // Symmetrical Unbreakable Terminal Header Bar
      React.createElement(
        'div',
        { className: 'terminal-header' },
        React.createElement(
          'div',
          { className: 'terminal-left' },
          React.createElement(
            'div',
            { className: 'terminal-dots' },
            React.createElement('span', { className: 'terminal-dot dot-red' }),
            React.createElement('span', { className: 'terminal-dot dot-yellow' }),
            React.createElement('span', { className: 'terminal-dot dot-green' })
          ),
          React.createElement('span', { className: 'terminal-title' }, 'zenith-core // live-telemetry-stream')
        ),
        React.createElement(
          'div',
          { className: 'terminal-right' },
          React.createElement(
            'div',
            {
              className: 'terminal-live-badge',
              onClick: () => setIsPaused(!isPaused),
              title: isPaused ? 'Click to resume stream' : 'Click to pause stream'
            },
            React.createElement('span', {
              className: 'terminal-live-dot',
              style: {
                backgroundColor: isPaused ? 'var(--accent-red)' : 'var(--accent-green)',
                boxShadow: isPaused ? '0 0 6px var(--accent-red)' : '0 0 6px var(--accent-green)'
              }
            }),
            React.createElement(
              'span',
              { style: { color: isPaused ? 'var(--accent-red)' : 'var(--accent-green)' } },
              isPaused ? '[PAUSED]' : '[SYNC ACTIVE]'
            )
          ),
          React.createElement(
            'button',
            {
              type: 'button',
              onClick: handleCopy,
              className: 'terminal-copy-action',
              style: copied
                ? { background: 'rgba(35, 165, 90, 0.2)', borderColor: 'var(--accent-green)', color: 'var(--accent-green)' }
                : {}
            },
            copied ? '[COPIED]' : 'Copy'
          )
        )
      ),
      // Terminal Body Stream
      React.createElement(
        'div',
        {
          ref: bodyRef,
          className: 'terminal-body',
          style: { maxHeight: '220px', overflowY: 'auto' }
        },
        logs.map((log) =>
          React.createElement(
            'div',
            {
              key: log.id,
              style: {
                animation: 'enter-fade 0.2s var(--m-ease-out) both',
                marginBottom: '0.25rem'
              }
            },
            React.createElement('span', { className: 'term-time' }, `[${log.time}] `),
            React.createElement(
              'span',
              { className: log.type === 'ok' ? 'term-tag-ok' : log.type === 'shield' ? 'term-tag-shield' : 'term-tag-warn' },
              `${log.tag} `
            ),
            log.text
          )
        )
      )
    );
  }

  // =========================================================================
  // 5. InteractivePipeline: Animated Defense Architecture Flow
  // =========================================================================
  function InteractivePipeline() {
    const [selectedStage, setSelectedStage] = useState(0);

    const stages = [
      {
        num: '01',
        title: 'Gateway Interception',
        desc: 'Intercepts incoming guild events and permission grants before members are exposed to unauthorized privilege escalations.',
        specs: ['Latency: < 0.2ms', 'Interceptor: Async Gateway Hook', 'Coverage: 100% Events']
      },
      {
        num: '02',
        title: 'In-Memory Security Shield',
        desc: 'Validates actor hierarchy, whitelists, and daily quota consumption with sub-millisecond RAM response.',
        specs: ['Cache: Redis + Local RAM', 'Evaluation: O(1) Matrix Lookup', 'Quotas: Rolling Windows']
      },
      {
        num: '03',
        title: 'Dual-Engine Persistence',
        desc: 'Reconstructs damaged channels and role hierarchies from serialized snapshots across PostgreSQL and SQLite.',
        specs: ['Sync: Bi-directional Engine', 'Snapshots: Instant Rollback', 'Integrity: Cryptographic Hash']
      }
    ];

    return React.createElement(
      'div',
      { style: { width: '100%', marginBottom: '4.5rem' } },
      React.createElement(
        'div',
        { className: 'architecture-flow', style: { marginBottom: '1.25rem' } },
        stages.map((st, idx) =>
          React.createElement(
            'div',
            {
              key: st.num,
              className: 'flow-step',
              onClick: () => setSelectedStage(idx),
              style: {
                cursor: 'pointer',
                border: selectedStage === idx ? '1px solid var(--accent-blue)' : '1px solid var(--glass-border)',
                background: selectedStage === idx ? 'rgba(88, 101, 242, 0.08)' : 'var(--glass-bg)',
                boxShadow: selectedStage === idx ? '0 12px 30px var(--accent-blue-glow)' : 'var(--glass-glow)',
                transition: 'all var(--m-out) var(--m-ease)'
              }
            },
            React.createElement('div', { className: 'flow-step-num' }, st.num),
            React.createElement('h3', { className: 'flow-title' }, st.title),
            React.createElement('p', { className: 'flow-desc' }, st.desc)
          )
        )
      ),
      // Active Node Inspector Card
      React.createElement(
        'div',
        {
          className: 'glass-card',
          style: {
            padding: '1.25rem 1.5rem',
            animation: 'enter-reveal 0.3s var(--m-ease-out) both',
            background: 'rgba(14, 15, 23, 0.85)'
          }
        },
        React.createElement(
          'div',
          { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' } },
          React.createElement(
            'div',
            null,
            React.createElement(
              'span',
              { style: { fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--accent-blue)' } },
              `STAGE ${stages[selectedStage].num} // ACTIVE DIAGNOSTIC TELEMETRY`
            ),
            React.createElement(
              'h4',
              { style: { fontSize: '1.05rem', fontWeight: '700', marginTop: '0.2rem' } },
              stages[selectedStage].title
            )
          ),
          React.createElement(
            'div',
            { style: { display: 'flex', gap: '0.75rem', flexWrap: 'wrap' } },
            stages[selectedStage].specs.map((sp) =>
              React.createElement(
                'span',
                {
                  key: sp,
                  style: {
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.75rem',
                    background: 'rgba(255, 255, 255, 0.04)',
                    border: '1px solid var(--glass-border)',
                    padding: '0.25rem 0.65rem',
                    borderRadius: '4px',
                    color: 'var(--text-secondary)'
                  }
                },
                sp
              )
            )
          )
        )
      )
    );
  }

  // =========================================================================
  // 6. InteractiveCommandMatrix: Stateful Search & Filtering
  // =========================================================================
  function InteractiveCommandMatrix() {
    const [search, setSearch] = useState('');
    const [category, setCategory] = useState('all');
    const [copiedTrigger, setCopiedTrigger] = useState(null);

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

    const handleCopy = (trigger) => {
      navigator.clipboard.writeText(`z!${trigger}`);
      setCopiedTrigger(trigger);
      setTimeout(() => setCopiedTrigger(null), 1800);
    };

    return React.createElement(
      'div',
      { className: 'command-explorer' },
      // Search Bar & Filter Controls
      React.createElement(
        'div',
        { style: { display: 'flex', gap: '1rem', marginBottom: '1.25rem', flexWrap: 'wrap' } },
        React.createElement('input', {
          type: 'text',
          placeholder: 'Search 504 commands by trigger or description...',
          value: search,
          onChange: (e) => setSearch(e.target.value),
          className: 'text-input',
          style: { flex: 1, minWidth: '240px' }
        })
      ),
      // Category Pills
      React.createElement(
        'div',
        { className: 'category-pills' },
        categories.map((cat) =>
          React.createElement(
            'button',
            {
              key: cat.id,
              type: 'button',
              className: `cat-pill ${category === cat.id ? 'active' : ''}`,
              onClick: () => setCategory(cat.id)
            },
            cat.label
          )
        )
      ),
      // Commands Table
      React.createElement(
        'div',
        { className: 'table-responsive' },
        React.createElement(
          'table',
          { className: 'cmd-table' },
          React.createElement(
            'thead',
            null,
            React.createElement(
              'tr',
              null,
              React.createElement('th', { style: { width: '30%' } }, 'Primary Trigger'),
              React.createElement('th', { style: { width: '22%' } }, 'Permission Level'),
              React.createElement('th', { style: { width: '38%' } }, 'Description'),
              React.createElement('th', { style: { width: '10%', textAlign: 'right' } }, 'Action')
            )
          ),
          React.createElement(
            'tbody',
            null,
            filtered.length === 0
              ? React.createElement(
                  'tr',
                  null,
                  React.createElement(
                    'td',
                    { colSpan: 4, style: { textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' } },
                    'No commands matched your query.'
                  )
                )
              : filtered.map((c) =>
                  React.createElement(
                    'tr',
                    { key: c.trigger },
                    React.createElement(
                      'td',
                      null,
                      React.createElement('span', { className: 'cmd-trigger' }, `z!${c.trigger}`)
                    ),
                    React.createElement(
                      'td',
                      null,
                      React.createElement(
                        'span',
                        { style: { fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-secondary)' } },
                        c.perms
                      )
                    ),
                    React.createElement('td', { style: { color: 'var(--text-secondary)' } }, c.desc),
                    React.createElement(
                      'td',
                      { style: { textAlign: 'right' } },
                      React.createElement(
                        'button',
                        {
                          type: 'button',
                          onClick: () => handleCopy(c.trigger),
                          className: 'btn btn-secondary btn-sm',
                          style: {
                            fontSize: '0.72rem',
                            padding: '0 0.6rem',
                            height: '28px',
                            background: copiedTrigger === c.trigger ? 'rgba(35, 165, 90, 0.2)' : '',
                            color: copiedTrigger === c.trigger ? 'var(--accent-green)' : ''
                          }
                        },
                        copiedTrigger === c.trigger ? '[OK]' : 'Copy'
                      )
                    )
                  )
                )
          )
        )
      )
    );
  }

  // =========================================================================
  // Mount Components to Target Containers
  // =========================================================================
  function initZenithReactComponents() {
    // 1. Mount Background Cyber Canvas
    const canvasContainer = document.getElementById('react-cyber-canvas-root');
    if (canvasContainer) {
      const root = ReactDOM.createRoot(canvasContainer);
      root.render(React.createElement(CyberGridPulse));
    }

    // 2. Mount Interactive Telemetry Terminal
    const terminalContainer = document.getElementById('react-terminal-root');
    if (terminalContainer) {
      const root = ReactDOM.createRoot(terminalContainer);
      root.render(React.createElement(InteractiveTelemetryTerminal));
    }

    // 3. Mount Interactive Architecture Pipeline
    const pipelineContainer = document.getElementById('react-pipeline-root');
    if (pipelineContainer) {
      const root = ReactDOM.createRoot(pipelineContainer);
      root.render(React.createElement(InteractivePipeline));
    }

    // 4. Mount Interactive Command Explorer
    const commandsContainer = document.getElementById('react-commands-root');
    if (commandsContainer) {
      const root = ReactDOM.createRoot(commandsContainer);
      root.render(React.createElement(InteractiveCommandMatrix));
    }
  }

  // Auto-initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initZenithReactComponents);
  } else {
    initZenithReactComponents();
  }

  // Export to global scope for flexibility
  window.ZenithReact = {
    CyberGridPulse,
    SpotlightCard,
    AnimatedCounter,
    InteractiveTelemetryTerminal,
    InteractivePipeline,
    InteractiveCommandMatrix
  };
})();
