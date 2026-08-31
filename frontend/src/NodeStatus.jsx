import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
const POLL_MS = 5000;

export default function NodeStatus() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [secondsAgo, setSecondsAgo] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let lastFetch = Date.now();

    async function poll() {
      try {
        const res = await fetch(`${API_BASE}/node-status`);
        if (!res.ok) throw new Error(`${res.status}`);
        const data = await res.json();
        if (!cancelled) {
          setStatus(data);
          setError(null);
          lastFetch = Date.now();
          setSecondsAgo(0);
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    }

    poll();
    const pollTimer = setInterval(poll, POLL_MS);
    const tickTimer = setInterval(() => {
      setSecondsAgo(Math.floor((Date.now() - lastFetch) / 1000));
    }, 1000);

    return () => {
      cancelled = true;
      clearInterval(pollTimer);
      clearInterval(tickTimer);
    };
  }, []);

  if (error) {
    return (
      <div className="node-status node-status-error">
        <span className="dot dot-red" /> node unreachable
      </div>
    );
  }

  if (!status) {
    return (
      <div className="node-status">
        <span className="dot dot-dim" /> connecting&hellip;
      </div>
    );
  }

  return (
    <div className="node-status" title="Polled live from GET /node-status">
      <span className="dot dot-green" />
      <span className="node-status-chain">{status.chain}</span>
      <span className="node-status-sep">&middot;</span>
      <span>height {status.blocks}</span>
      <span className="node-status-sep">&middot;</span>
      <span className="node-status-hash">tip {status.bestblockhash.slice(0, 10)}&hellip;</span>
      <span className="node-status-sep">&middot;</span>
      <span className="node-status-ping">checked {secondsAgo}s ago</span>
    </div>
  );
}
