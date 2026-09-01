import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
const POLL_MS = 4000;

function LivePulse() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [secondsAgo, setSecondsAgo] = useState(0);
  const [pingMs, setPingMs] = useState(null);

  useEffect(() => {
    let cancelled = false;
    let lastFetch = Date.now();

    async function poll() {
      const start = performance.now();
      try {
        const res = await fetch(`${API_BASE}/node-status`);
        if (!res.ok) throw new Error(`${res.status}`);
        const data = await res.json();
        const rtt = Math.round(performance.now() - start);
        if (!cancelled) {
          setStatus(data);
          setPingMs(rtt);
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
      <div className="live-pulse live-pulse-error">
        <span className="dot dot-red" /> Node unreachable: {error}
      </div>
    );
  }

  if (!status) {
    return (
      <div className="live-pulse">
        <span className="dot dot-dim" /> Connecting to the node&hellip;
      </div>
    );
  }

  return (
    <div className="live-pulse">
      <div className="live-pulse-row">
        <span className="dot dot-green" />
        <span className="live-pulse-label">Live right now</span>
      </div>
      <div className="live-pulse-grid">
        <div>
          <span className="live-pulse-k">chain</span>
          <span className="live-pulse-v">{status.chain}</span>
        </div>
        <div>
          <span className="live-pulse-k">height</span>
          <span className="live-pulse-v">{status.blocks}</span>
        </div>
        <div>
          <span className="live-pulse-k">round trip</span>
          <span className="live-pulse-v">{pingMs}ms</span>
        </div>
        <div>
          <span className="live-pulse-k">last polled</span>
          <span className="live-pulse-v">{secondsAgo}s ago</span>
        </div>
        <div className="live-pulse-full">
          <span className="live-pulse-k">tip</span>
          <span className="live-pulse-v mono">{status.bestblockhash}</span>
        </div>
      </div>
      <p className="live-pulse-note">
        This box polls <code>GET /node-status</code> every {POLL_MS / 1000}s, live, in your
        browser, right now. The round-trip time will jitter a little from poll to poll -- that's
        not decoration, it's a real network round trip to a real process.
      </p>
    </div>
  );
}

export default function AboutNode() {
  const [info, setInfo] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/node-info`)
      .then(async (r) => {
        if (!r.ok) throw new Error(`server returned ${r.status}`);
        return r.json();
      })
      .then(setInfo)
      .catch((e) => setError(`Could not load node info: ${e.message}`));
  }, []);

  return (
    <div className="home-page">
      <div className="home-eyebrow">About</div>
      <h2>The Node</h2>

      {error && <div className="error-banner">{error}</div>}

      <p className="home-copy">
        Every verdict in this app comes from an actual Bitcoin Core node
        {info ? (
          <>
            {" "}
            &mdash; <code>{info.subversion}</code>
          </>
        ) : (
          ""
        )}{" "}
        &mdash; running locally in <strong>regtest</strong> mode. Nothing in this app is
        simulated or hardcoded. Every query is that node's real
        answer to a real RPC call.  
      </p>

      <LivePulse />

      <h3 className="home-subhead">The frozen chain</h3>
      <p className="home-copy">
        Bitcoin normally needs a wallet, a mined chain, and time for coins to mature. To the public 
        share one node, this node was mined <strong>once</strong>, and then frozen. . Every scenario proves
        this by never broadcasting or mutating anything: it only ever asks the node "would you
        accept this?" through read-only RPC calls (<code>testmempoolaccept</code>, and{" "}
        <code>getblocktemplate</code> in proposal mode), so the tip below never moves no matter
        how many people are using this at once.
      </p>

      {info && (
        <div className="node-facts">
          <div className="node-fact">
            <span className="node-fact-k">frozen tip height</span>
            <span className="node-fact-v">{info.frozen_tip_height}</span>
          </div>
          <div className="node-fact">
            <span className="node-fact-k">frozen tip hash</span>
            <span className="node-fact-v mono">{info.frozen_tip_hash}</span>
          </div>
          <div className="node-fact">
            <span className="node-fact-k">mining address</span>
            <span className="node-fact-v mono">{info.mining_address}</span>
          </div>
        </div>
      )}

      <h3 className="home-subhead">Pre-loaded fixtures</h3>
      <p className="home-copy">
        To keep things simple, two UTXOs were set up ahead of time and are reused by every scenario that needs to spend
        something real. One still spendable, one deliberately already spent (for Double Spend):
      </p>

      {info && (
        <div className="fixture-table">
          {Object.entries(info.utxos).map(([key, utxo]) => (
            <div className="fixture-row" key={key}>
              <div className="fixture-name">{key}</div>
              <div className="fixture-detail">
                <span>txid</span>
                <code>{utxo.txid}</code>
              </div>
              <div className="fixture-detail">
                <span>vout</span>
                <code>{utxo.vout}</code>
              </div>
              <div className="fixture-detail">
                <span>amount</span>
                <code>{utxo.amount} BTC</code>
              </div>
              <div className="fixture-detail">
                <span>address</span>
                <code>{utxo.address}</code>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
