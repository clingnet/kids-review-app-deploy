/**
 * bg.js — 全局背景动画（深空星辰 + 电路数据光线）
 * 增强版：星点更亮更多、脉冲更明显、暗角适度保留。
 */
(function () {
  'use strict';

  /* ── 配色 ── */
  const CYAN    = { r: 45,  g: 226, b: 230 };
  const PURPLE  = { r: 168, g: 85,  b: 247 };
  const MAGENTA = { r: 255, g: 45,  b: 120 };

  /* ── 参数（增强版） ── */
  const STAR_COUNT     = 320;  // 更多星点
  const CIRCUIT_COUNT  = 16;   // 更多电路线
  const PULSE_COUNT    = 28;   // 更多光脉冲

  /* ── 创建 canvas ── */
  const canvas = document.createElement('canvas');
  canvas.id = 'globalBg';
  Object.assign(canvas.style, {
    position:      'fixed',
    inset:         '0',
    zIndex:        '0',
    pointerEvents: 'none',
    display:       'block',
  });
  document.body.insertBefore(canvas, document.body.firstChild);

  const ctx = canvas.getContext('2d');

  /* ── 尺寸 ── */
  let W = 0, H = 0;

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
    initCircuits();
  }

  /* ══════════════════════════════════════════════
     星点（增强：更亮、更大、彩色占比更高）
  ══════════════════════════════════════════════ */
  const stars = [];

  function initStars() {
    stars.length = 0;
    for (let i = 0; i < STAR_COUNT; i++) {
      const palette = Math.random();
      let cr, cg, cb;
      if (palette < 0.14) {
        cr = CYAN.r;   cg = CYAN.g;   cb = CYAN.b;
      } else if (palette < 0.24) {
        cr = PURPLE.r; cg = PURPLE.g; cb = PURPLE.b;
      } else if (palette < 0.29) {
        cr = MAGENTA.r; cg = MAGENTA.g; cb = MAGENTA.b;
      } else {
        cr = 190 + Math.random() * 60;
        cg = 205 + Math.random() * 45;
        cb = 225 + Math.random() * 30;
      }
      stars.push({
        x:     Math.random() * window.innerWidth,
        y:     Math.random() * window.innerHeight,
        r:     Math.random() * 1.6 + 0.2,   // 稍大
        vx:    (Math.random() - 0.5) * 0.05,
        vy:    Math.random() * 0.035 + 0.008,
        alpha: Math.random() * 0.55 + 0.15,  // 基础亮度提高
        phase: Math.random() * Math.PI * 2,
        speed: Math.random() * 0.009 + 0.003,
        cr, cg, cb,
      });
    }
  }

  function updateStars(t) {
    stars.forEach(s => {
      s.x += s.vx;
      s.y += s.vy;
      if (s.x < 0) s.x = W;
      if (s.x > W) s.x = 0;
      if (s.y > H) { s.y = 0; s.x = Math.random() * W; }
      // 明灭范围加宽：0.12 ~ 0.68
      s.alpha = 0.12 + 0.56 * (0.5 + 0.5 * Math.sin(t * s.speed * 60 + s.phase));
    });
  }

  function drawStars() {
    stars.forEach(s => {
      // 彩色星加一圈柔和光晕
      if (s.r > 1.0 && (s.cr !== 190)) {
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r * 2.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${s.cr},${s.cg},${s.cb},${s.alpha * 0.18})`;
        ctx.fill();
      }
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${s.cr},${s.cg},${s.cb},${s.alpha})`;
      ctx.fill();
    });
  }

  /* ══════════════════════════════════════════════
     电路/数据光线（增强：线条更亮、脉冲更明显）
  ══════════════════════════════════════════════ */
  const circuits = [];

  function genCircuitPath() {
    const pts = [];
    const side = Math.floor(Math.random() * 4);
    let x0, y0;
    if (side === 0) { x0 = Math.random() * W; y0 = 0; }
    else if (side === 1) { x0 = W; y0 = Math.random() * H; }
    else if (side === 2) { x0 = Math.random() * W; y0 = H; }
    else { x0 = 0; y0 = Math.random() * H; }
    pts.push({ x: x0, y: y0 });

    const bends = 1 + Math.floor(Math.random() * 3);
    let cx = x0, cy = y0;
    let horiz = Math.random() < 0.5;
    for (let i = 0; i < bends; i++) {
      if (horiz) {
        cx = clamp(cx + (Math.random() - 0.4) * W * 0.5, 0.05 * W, 0.95 * W);
      } else {
        cy = clamp(cy + (Math.random() - 0.4) * H * 0.5, 0.05 * H, 0.95 * H);
      }
      pts.push({ x: cx, y: cy });
      horiz = !horiz;
    }

    const last = pts[pts.length - 1];
    pts.push({
      x: clamp(last.x + (Math.random() - 0.5) * W * 0.6, 0, W),
      y: clamp(last.y + (Math.random() - 0.5) * H * 0.6, 0, H),
    });

    return pts;
  }

  function totalPathLen(pts) {
    let len = 0;
    for (let i = 1; i < pts.length; i++) {
      const dx = pts[i].x - pts[i-1].x;
      const dy = pts[i].y - pts[i-1].y;
      len += Math.sqrt(dx*dx + dy*dy);
    }
    return len;
  }

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function pickColor() {
    const r = Math.random();
    if (r < 0.45) return CYAN;
    if (r < 0.75) return PURPLE;
    return MAGENTA;
  }

  function initCircuits() {
    circuits.length = 0;
    for (let i = 0; i < CIRCUIT_COUNT; i++) {
      const col  = pickColor();
      const pts  = genCircuitPath();
      const tlen = totalPathLen(pts);
      circuits.push({
        pts,
        tlen,
        col,
        lineAlpha: 0.07 + Math.random() * 0.11,  // 增强：线条更亮
        lineW:  0.5 + Math.random() * 0.8,
      });
    }
    pulses.length = 0;
    for (let i = 0; i < PULSE_COUNT; i++) {
      spawnPulse();
    }
  }

  /* ── 光脉冲（增强：更亮、更宽、更长） ── */
  const pulses = [];

  function spawnPulse() {
    const cidx = Math.floor(Math.random() * circuits.length);
    const c    = circuits[cidx];
    pulses.push({
      cidx,
      t:      Math.random(),
      speed:  0.001 + Math.random() * 0.0018,   // 稍快
      len:    0.06 + Math.random() * 0.10,        // 更长
      alpha:  0.7 + Math.random() * 0.3,          // 更亮
      col:    c.col,
      width:  1.8 + Math.random() * 2.0,          // 更宽
    });
  }

  function pathPoint(pts, tlen, t) {
    const target = t * tlen;
    let acc = 0;
    for (let i = 1; i < pts.length; i++) {
      const dx  = pts[i].x - pts[i-1].x;
      const dy  = pts[i].y - pts[i-1].y;
      const seg = Math.sqrt(dx*dx + dy*dy);
      if (acc + seg >= target) {
        const frac = (target - acc) / seg;
        return {
          x: pts[i-1].x + dx * frac,
          y: pts[i-1].y + dy * frac,
        };
      }
      acc += seg;
    }
    return pts[pts.length - 1];
  }

  function drawCircuits() {
    // 静态线条
    circuits.forEach(c => {
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(c.pts[0].x, c.pts[0].y);
      for (let i = 1; i < c.pts.length; i++) {
        ctx.lineTo(c.pts[i].x, c.pts[i].y);
      }
      ctx.strokeStyle = `rgba(${c.col.r},${c.col.g},${c.col.b},${c.lineAlpha})`;
      ctx.lineWidth   = c.lineW;
      ctx.stroke();
      ctx.restore();
    });

    // 光脉冲（增强：尾部更长，头部更亮，加强 shadowBlur）
    pulses.forEach(p => {
      const c   = circuits[p.cidx];
      const t0  = Math.max(0, p.t - p.len);
      const t1  = Math.min(1, p.t);
      if (t1 <= t0) return;

      const steps = 16;
      ctx.save();
      for (let s = 0; s < steps; s++) {
        const ta = t0 + (t1 - t0) * (s / steps);
        const tb = t0 + (t1 - t0) * ((s + 1) / steps);
        const pa = pathPoint(c.pts, c.tlen, ta);
        const pb = pathPoint(c.pts, c.tlen, tb);
        const frac = s / steps;
        const a = p.alpha * frac * 0.75;   // 头部更亮
        ctx.beginPath();
        ctx.moveTo(pa.x, pa.y);
        ctx.lineTo(pb.x, pb.y);
        ctx.strokeStyle = `rgba(${c.col.r},${c.col.g},${c.col.b},${a})`;
        ctx.lineWidth   = p.width * (0.2 + frac * 0.8);
        ctx.shadowBlur  = 10 * frac;        // 加强光晕
        ctx.shadowColor = `rgba(${c.col.r},${c.col.g},${c.col.b},0.8)`;
        ctx.stroke();
      }
      ctx.restore();

      p.t += p.speed;
      if (p.t - p.len > 1) {
        const cidx = Math.floor(Math.random() * circuits.length);
        p.cidx  = cidx;
        p.col   = circuits[cidx].col;
        p.t     = 0;
        p.speed = 0.001 + Math.random() * 0.0018;
        p.len   = 0.06 + Math.random() * 0.10;
        p.alpha = 0.7 + Math.random() * 0.3;
        p.width = 1.8 + Math.random() * 2.0;
      }
    });
  }

  /* ══════════════════════════════════════════════
     暗角遮罩（适度保留，不过深）
  ══════════════════════════════════════════════ */
  function drawVignette() {
    const grad = ctx.createRadialGradient(
      W * 0.5, H * 0.5, H * 0.28,
      W * 0.5, H * 0.5, H * 0.92
    );
    grad.addColorStop(0, 'rgba(10,14,26,0)');
    grad.addColorStop(1, 'rgba(10,14,26,0.45)');   // 比原来浅，内容更可见
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, H);
  }

  /* ══════════════════════════════════════════════
     主循环
  ══════════════════════════════════════════════ */
  let t = 0;

  function frame() {
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#0a0e1a';
    ctx.fillRect(0, 0, W, H);

    t += 0.016;
    updateStars(t);
    drawStars();
    drawCircuits();
    drawVignette();

    requestAnimationFrame(frame);
  }

  /* ── 初始化 ── */
  initStars();
  window.addEventListener('resize', resize);
  resize();
  frame();

})();
