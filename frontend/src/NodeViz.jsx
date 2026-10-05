import { useEffect, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
const STATUS_POLL_MS = 5000;
// Matches the backend cache TTL; polling faster would only re-read the cache.
const MAINNET_POLL_MS = 30000;
const TAU = Math.PI * 2;
// The chain enters the node from the left, so the rule ring leaves a gap there.
const ARC_START = (-150 * Math.PI) / 180;
const ARC_SPAN = (300 * Math.PI) / 180;
const SEG_GAP = 0.06;

function readTheme(el) {
  const css = getComputedStyle(el);
  const v = (name) => css.getPropertyValue(name).trim();
  return {
    panel: v("--bg-panel"),
    raised: v("--bg-panel-raised"),
    border: v("--border"),
    text: v("--text"),
    dim: v("--text-dim"),
    faint: v("--text-faint"),
    accent: v("--accent"),
    danger: v("--danger"),
    mono: v("--mono"),
  };
}

function withAlpha(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}

function ago(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  return m < 60 ? `${m}m ago` : `${Math.floor(m / 60)}h ${m % 60}m ago`;
}

function segmentAngles(i, n) {
  const span = ARC_SPAN / n;
  const start = ARC_START + i * span + SEG_GAP / 2;
  return { start, end: start + span - SEG_GAP };
}

// Angle in (-PI, PI], mapped to a segment index or -1 for the chain-side gap.
function segmentAt(angle, n) {
  if (n === 0) return -1;
  const rel = angle - ARC_START;
  if (rel < 0 || rel > ARC_SPAN) return -1;
  return Math.min(n - 1, Math.floor(rel / (ARC_SPAN / n)));
}

function nearestSegment(angle, n) {
  const direct = segmentAt(angle, n);
  if (direct !== -1) return direct;
  return angle > 0 ? n - 1 : 0;
}

function usePoll(path, ms) {
  const [data, setData] = useState(null);
  const [ok, setOk] = useState(null);
  const [rtt, setRtt] = useState(null);
  useEffect(() => {
    let cancelled = false;
    async function poll() {
      const start = performance.now();
      try {
        const res = await fetch(`${API_BASE}${path}`);
        if (!res.ok) throw new Error(`${res.status}`);
        const body = await res.json();
        if (cancelled) return;
        setData(body);
        setRtt(Math.round(performance.now() - start));
        setOk(true);
      } catch {
        if (!cancelled) setOk(false);
      }
    }
    poll();
    const timer = setInterval(poll, ms);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [path, ms]);
  return { data, ok, rtt };
}

// Left: recent mainnet blocks from a public explorer (backend/livechain.py).
// Right: our regtest node, ringed by the rules this app's scenarios break.
// The link between them is dashed on purpose: our node does not follow
// mainnet, and the drawing must not imply that it does.
export default function NodeViz({ scenarios, onSelectScenario }) {
  const wrapRef = useRef(null);
  const canvasRef = useRef(null);
  const scenariosRef = useRef(scenarios);
  const onSelectRef = useRef(onSelectScenario);
  const mainnetRef = useRef(null);
  const nodeRef = useRef(null);
  const node = usePoll("/node-status", STATUS_POLL_MS);
  const mainnet = usePoll("/mainnet-blocks", MAINNET_POLL_MS);
  const [now, setNow] = useState(() => Date.now() / 1000);

  // The draw loop runs outside React; it reads the latest values through refs.
  useEffect(() => {
    scenariosRef.current = scenarios;
    onSelectRef.current = onSelectScenario;
  }, [scenarios, onSelectScenario]);

  useEffect(() => {
    mainnetRef.current = mainnet.data;
  }, [mainnet.data]);

  useEffect(() => {
    nodeRef.current = node.ok ? node.data : null;
  }, [node.ok, node.data]);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const theme = readTheme(canvas);
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let w = 0;
    let h = 0;
    let geo = null;
    let raf = 0;
    let visible = true;
    let last = performance.now();
    let spawnIn = 0.8;
    // When a new mainnet block lands, the chain starts shifted right by one
    // slot per new block and eases back, so blocks visibly advance.
    let shift = 0;
    let lastTipHeight = null;
    const mouse = { x: -1, y: -1, inside: false };
    const payloads = [];
    const marks = [];
    const log = [];
    const flashes = [];

    function layout() {
      const rect = wrap.getBoundingClientRect();
      w = Math.max(280, Math.round(rect.width));
      const narrow = w < 520;
      h = narrow ? 240 : 270;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      geo = {
        cx: Math.round(w * (narrow ? 0.66 : 0.68)),
        cy: Math.round(h / 2),
        boxW: narrow ? 78 : 84,
        boxH: 34,
        shieldR: narrow ? 64 : 78,
        block: 16,
        blockGap: narrow ? 8 : 10,
      };
    }

    function chainSlots() {
      const { cx, cy, shieldR, block, blockGap } = geo;
      const blocks = mainnetRef.current?.blocks || [];
      const out = [];
      let x = cx - shieldR - 34 + shift;
      for (let k = 0; x - block / 2 > 8; k++) {
        out.push({ k, x, y: cy, b: blocks[k] || null });
        x -= block + blockGap;
      }
      return out;
    }

    function hoveredSegment() {
      if (!mouse.inside) return -1;
      const dx = mouse.x - geo.cx;
      const dy = mouse.y - geo.cy;
      if (Math.abs(Math.hypot(dx, dy) - geo.shieldR) > 14) return -1;
      return segmentAt(Math.atan2(dy, dx), scenariosRef.current.length);
    }

    function hoveredBlock() {
      if (!mouse.inside) return null;
      const half = geo.block / 2 + 4;
      return (
        chainSlots().find(
          (s) => s.b && Math.abs(mouse.x - s.x) < half && Math.abs(mouse.y - s.y) < half,
        ) || null
      );
    }

    function spawn(seg, from) {
      const list = scenariosRef.current;
      if (!list.length) return;
      const { cx, cy, shieldR } = geo;
      const { start, end } = segmentAngles(seg, list.length);
      const hitAngle = start + (0.25 + Math.random() * 0.5) * (end - start);
      let sx;
      let sy;
      if (from) {
        sx = from.x;
        sy = from.y;
      } else {
        const a = hitAngle + (Math.random() - 0.5) * 0.4;
        const dx = Math.cos(a);
        const dy = Math.sin(a);
        const tx = dx > 0 ? (w - cx) / dx : dx < 0 ? -cx / dx : Infinity;
        const ty = dy > 0 ? (h - cy) / dy : dy < 0 ? -cy / dy : Infinity;
        const d = Math.min(tx, ty) + 8;
        sx = cx + dx * d;
        sy = cy + dy * d;
      }
      const ex = cx + Math.cos(hitAngle) * shieldR;
      const ey = cy + Math.sin(hitAngle) * shieldR;
      const len = Math.max(1, Math.hypot(ex - sx, ey - sy));
      payloads.push({
        seg,
        kind: list[seg].kind,
        sx,
        sy,
        ex,
        ey,
        t: 0,
        rate: (from ? 160 : 90) / len,
        hitAngle,
      });
    }

    function reject(p) {
      const s = scenariosRef.current[p.seg];
      flashes[p.seg] = 1;
      marks.push({ x: p.ex, y: p.ey, age: 0 });
      // A fixed log in the corner instead of labels at each hit point, so
      // rapid clicks stack into tidy rows rather than scattering text.
      log.unshift({ text: s ? `rejected: ${s.title.toLowerCase()}` : "rejected", age: 0 });
      log.length = Math.min(log.length, w < 520 ? 3 : 4);
    }

    function step(dt) {
      const tip = mainnetRef.current?.blocks?.[0]?.height ?? null;
      if (tip !== null) {
        if (lastTipHeight !== null && tip > lastTipHeight && !reduceMotion) {
          shift += (tip - lastTipHeight) * (geo.block + geo.blockGap);
        }
        lastTipHeight = tip;
      }
      shift *= Math.pow(0.02, dt);
      if (shift < 0.3) shift = 0;

      if (!reduceMotion) {
        spawnIn -= dt;
        if (spawnIn <= 0 && scenariosRef.current.length) {
          spawn(Math.floor(Math.random() * scenariosRef.current.length));
          spawnIn = 1.8 + Math.random() * 1.6;
        }
      }
      for (let i = payloads.length - 1; i >= 0; i--) {
        const p = payloads[i];
        if (p.returning) {
          // Rejected: retrace the incoming path at the same speed, fading out.
          p.t -= p.rate * dt;
          p.backAge += dt;
          if (p.t <= 0 || p.backAge > 0.8) payloads.splice(i, 1);
          continue;
        }
        p.t = Math.min(1, p.t + p.rate * dt);
        if (p.t >= 1) {
          reject(p);
          p.returning = true;
          p.backAge = 0;
        }
      }
      for (let i = marks.length - 1; i >= 0; i--) {
        marks[i].age += dt;
        if (marks[i].age > 2) marks.splice(i, 1);
      }
      for (let i = log.length - 1; i >= 0; i--) {
        log[i].age += dt;
        if (log[i].age > 4) log.splice(i, 1);
      }
      for (let i = 0; i < flashes.length; i++) {
        if (flashes[i]) flashes[i] = Math.max(0, flashes[i] - dt * 1.2);
      }
    }

    function drawChain(hover) {
      const { cx, cy, boxW, block } = geo;
      const slots = chainSlots();
      const tip = slots[0];
      const data = mainnetRef.current;

      // Dashed: the chain is mainnet, the node is regtest; nothing syncs.
      ctx.setLineDash([3, 4]);
      ctx.strokeStyle = theme.faint;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(tip.x + block / 2, cy + 0.5);
      ctx.lineTo(cx - boxW / 2, cy + 0.5);
      ctx.stroke();
      ctx.setLineDash([]);

      slots.forEach((s, i) => {
        const fade = Math.max(0.15, 1 - i / slots.length);
        if (i > 0) {
          ctx.strokeStyle = withAlpha(theme.faint, fade * 0.7);
          ctx.beginPath();
          ctx.moveTo(s.x + block / 2, cy + 0.5);
          ctx.lineTo(slots[i - 1].x - block / 2, cy + 0.5);
          ctx.stroke();
        }
        const isHover = hover && hover.k === s.k;
        ctx.fillStyle = theme.panel;
        ctx.fillRect(s.x - block / 2, cy - block / 2, block, block);
        ctx.strokeStyle = !s.b
          ? withAlpha(theme.border, fade)
          : i === 0 || isHover
            ? theme.accent
            : withAlpha(theme.dim, fade);
        ctx.strokeRect(s.x - block / 2 + 0.5, cy - block / 2 + 0.5, block - 1, block - 1);
      });

      ctx.font = `10px ${theme.mono}`;
      ctx.textAlign = "left";
      ctx.fillStyle = theme.faint;
      ctx.fillText("mainnet", slots[slots.length - 1].x - block / 2, cy - block / 2 - 24);

      ctx.textAlign = "center";
      if (data?.blocks?.length) {
        const b = data.blocks[0];
        ctx.fillStyle = theme.dim;
        ctx.fillText(`#${b.height.toLocaleString()}`, tip.x, cy - block / 2 - 8);
        ctx.fillStyle = theme.faint;
        ctx.fillText(ago(Date.now() / 1000 - b.timestamp), tip.x, cy + block / 2 + 15);
      } else {
        ctx.fillStyle = theme.faint;
        ctx.fillText("…", tip.x, cy - block / 2 - 8);
      }

      if (hover && hover.k > 0) {
        const b = hover.b;
        ctx.fillStyle = theme.dim;
        ctx.fillText(`#${b.height.toLocaleString()}`, hover.x, cy + block / 2 + 30);
        ctx.fillStyle = theme.faint;
        ctx.fillText(`${b.tx_count.toLocaleString()} tx`, hover.x, cy + block / 2 + 43);
      } else if (hover) {
        ctx.fillStyle = theme.faint;
        ctx.fillText(`${hover.b.tx_count.toLocaleString()} tx`, hover.x, cy + block / 2 + 30);
      }
    }

    function drawRing(hoverSeg) {
      const list = scenariosRef.current;
      const { cx, cy, shieldR } = geo;
      ctx.lineCap = "butt";
      if (!list.length) {
        ctx.strokeStyle = theme.border;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx, cy, shieldR, ARC_START, ARC_START + ARC_SPAN);
        ctx.stroke();
        return;
      }
      list.forEach((s, i) => {
        const { start, end } = segmentAngles(i, list.length);
        const flash = flashes[i] || 0;
        ctx.strokeStyle =
          i === hoverSeg
            ? theme.accent
            : flash > 0
              ? withAlpha(theme.danger, 0.35 + flash * 0.65)
              : theme.border;
        ctx.lineWidth = i === hoverSeg ? 4 : 2;
        ctx.beginPath();
        ctx.arc(cx, cy, shieldR, start, end);
        ctx.stroke();
      });
    }

    function drawNode(status) {
      const { cx, cy, boxW, boxH } = geo;
      ctx.fillStyle = theme.raised;
      ctx.fillRect(cx - boxW / 2, cy - boxH / 2, boxW, boxH);
      ctx.strokeStyle = status ? theme.accent : theme.faint;
      ctx.lineWidth = 1;
      ctx.strokeRect(cx - boxW / 2 + 0.5, cy - boxH / 2 + 0.5, boxW - 1, boxH - 1);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.font = `11px ${theme.mono}`;
      ctx.fillStyle = theme.text;
      ctx.fillText("bitcoind", cx, cy - 6);
      ctx.font = `9px ${theme.mono}`;
      ctx.fillStyle = theme.faint;
      ctx.fillText(status ? `${status.chain} #${status.blocks}` : "offline", cx, cy + 8);
      ctx.textBaseline = "alphabetic";
    }

    function drawPayloads() {
      for (const p of payloads) {
        const x = p.sx + (p.ex - p.sx) * p.t;
        const y = p.sy + (p.ey - p.sy) * p.t;
        const a = p.returning ? Math.max(0, 1 - p.backAge / 0.8) : 1;
        const back = p.returning ? Math.min(1, p.t + 0.06) : Math.max(0, p.t - 0.06);
        ctx.strokeStyle = withAlpha(theme.dim, 0.35 * a);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(p.sx + (p.ex - p.sx) * back, p.sy + (p.ey - p.sy) * back);
        ctx.lineTo(x, y);
        ctx.stroke();
        ctx.fillStyle = withAlpha(theme.dim, a);
        if (p.kind === "block") {
          ctx.fillRect(x - 3, y - 3, 6, 6);
        } else {
          ctx.beginPath();
          ctx.arc(x, y, 2.5, 0, TAU);
          ctx.fill();
        }
      }
      for (const m of marks) {
        const a = Math.max(0, 1 - Math.max(0, m.age - 0.8) / 1.2);
        ctx.strokeStyle = withAlpha(theme.danger, a);
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(m.x - 3, m.y - 3);
        ctx.lineTo(m.x + 3, m.y + 3);
        ctx.moveTo(m.x + 3, m.y - 3);
        ctx.lineTo(m.x - 3, m.y + 3);
        ctx.stroke();
      }
      ctx.font = `10px ${theme.mono}`;
      ctx.textAlign = "left";
      log.forEach((entry, i) => {
        const a = Math.max(0, 1 - Math.max(0, entry.age - 2.5) / 1.5);
        ctx.fillStyle = withAlpha(theme.danger, a * (i === 0 ? 1 : 0.7));
        ctx.fillText("\u2715", 12, 20 + i * 15);
        ctx.fillStyle = withAlpha(i === 0 ? theme.dim : theme.faint, a);
        ctx.fillText(entry.text, 26, 20 + i * 15);
      });
    }

    function drawTooltip(seg) {
      const s = scenariosRef.current[seg];
      if (!s) return;
      const text = `${s.title} (${s.kind}) → open`;
      ctx.font = `11px ${theme.mono}`;
      const bw = ctx.measureText(text).width + 14;
      const bh = 22;
      let x = mouse.x + 12;
      let y = mouse.y + 12;
      if (x + bw > w - 4) x = mouse.x - bw - 12;
      if (y + bh > h - 4) y = mouse.y - bh - 12;
      ctx.fillStyle = theme.raised;
      ctx.fillRect(x, y, bw, bh);
      ctx.strokeStyle = theme.border;
      ctx.lineWidth = 1;
      ctx.strokeRect(x + 0.5, y + 0.5, bw - 1, bh - 1);
      ctx.textAlign = "left";
      ctx.fillStyle = theme.text;
      ctx.fillText(text, x + 7, y + 15);
    }

    function draw() {
      const hoverSeg = hoveredSegment();
      const hoverBlock = hoverSeg === -1 ? hoveredBlock() : null;
      ctx.clearRect(0, 0, w, h);
      drawChain(hoverBlock);
      drawRing(hoverSeg);
      drawPayloads();
      drawNode(nodeRef.current);
      if (hoverSeg !== -1) drawTooltip(hoverSeg);
      canvas.style.cursor = hoverSeg !== -1 ? "pointer" : "crosshair";
    }

    function frame(t) {
      const dt = Math.min(0.05, (t - last) / 1000);
      last = t;
      step(dt);
      draw();
      raf = visible ? requestAnimationFrame(frame) : 0;
    }

    function start() {
      if (raf) return;
      last = performance.now();
      raf = requestAnimationFrame(frame);
    }

    function toLocal(e) {
      const rect = canvas.getBoundingClientRect();
      return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }

    function onMove(e) {
      Object.assign(mouse, toLocal(e), { inside: true });
    }

    function onLeave() {
      mouse.inside = false;
    }

    function onClick(e) {
      const p = toLocal(e);
      Object.assign(mouse, p, { inside: true });
      const list = scenariosRef.current;
      const seg = hoveredSegment();
      if (seg !== -1) {
        onSelectRef.current(list[seg].id);
        return;
      }
      const dx = p.x - geo.cx;
      const dy = p.y - geo.cy;
      if (Math.hypot(dx, dy) < geo.shieldR + 16 || !list.length) return;
      spawn(nearestSegment(Math.atan2(dy, dx), list.length), p);
    }

    layout();
    const ro = new ResizeObserver(layout);
    ro.observe(wrap);
    const io = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible) start();
    });
    io.observe(canvas);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerleave", onLeave);
    canvas.addEventListener("click", onClick);
    start();

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerleave", onLeave);
      canvas.removeEventListener("click", onClick);
    };
  }, []);

  const tip = mainnet.data?.blocks?.[0];

  return (
    <figure className="node-viz" ref={wrapRef}>
      <canvas
        ref={canvasRef}
        role="img"
        aria-label="Recent mainnet blocks on the left; our regtest bitcoind node on the right, ringed by the rules this app's scenarios break. Payloads fly in and are rejected."
      />
      <figcaption className="node-viz-caption">
        <div className="node-viz-legend">
          <span>
            <span className={`dot ${node.ok ? "dot-green" : node.ok === false ? "dot-red" : "dot-dim"}`} />
            our node: {node.ok ? `${node.data.chain} #${node.data.blocks}, ${node.rtt}ms` : node.ok === false ? "unreachable" : "connecting…"}
          </span>
          <span>
            mainnet:{" "}
            {tip
              ? `#${tip.height.toLocaleString()}, ${ago(now - tip.timestamp)} (via ${mainnet.data.source}${mainnet.data.stale ? ", stale" : ""})`
              : mainnet.ok === false
                ? "unavailable"
                : "loading…"}
          </span>
        </div>
        <div className="node-viz-hint">
          Our node is not synced to mainnet; it validates against its own frozen regtest chain.
          Click anywhere to throw a payload, or click a ring segment to open that scenario.
        </div>
      </figcaption>
    </figure>
  );
}
