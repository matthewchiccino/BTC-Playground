import { useEffect, useState } from "react";
import "./App.css";
import DecodedView from "./DecodedView";
import HexDiff from "./HexDiff";
import HomePage from "./HomePage";
import NodeStatus from "./NodeStatus";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

async function throwForStatus(res) {
  if (res.ok) return;
  let detail = `server returned ${res.status}`;
  try {
    const body = await res.json();
    if (body?.detail) detail = body.detail;
  } catch {
    // body wasn't JSON -- fall back to the status-based message above
  }
  throw new Error(detail);
}

const STEPS = ["build", "submit", "response", "verdict"];
const STEP_LABEL = {
  build: "1. Build",
  submit: "2. Submit",
  response: "3. Response",
  verdict: "4. Verdict",
};

function StepTracker({ stage }) {
  const activeIndex = {
    selected: -1,
    building: 0,
    built: 0,
    submitting: 1,
    response: 2,
    revealed: 3,
  }[stage];

  return (
    <div className="step-tracker">
      {STEPS.map((step, i) => (
        <span
          key={step}
          className={`step-chip ${i <= activeIndex ? "step-done" : ""} ${i === activeIndex ? "step-current" : ""}`}
        >
          {STEP_LABEL[step]}
        </span>
      ))}
    </div>
  );
}

function RuleTypeBadge({ ruleType }) {
  if (!ruleType) return null;
  return <span className={`rule-type-badge ${ruleType}`}>{ruleType} rule</span>;
}

export default function App() {
  const [scenarios, setScenarios] = useState([]);
  const [view, setView] = useState("home"); // "home" | "scenario"
  const [selectedId, setSelectedId] = useState(null);
  const [stage, setStage] = useState("selected"); // selected -> building -> built -> submitting -> response -> revealed
  const [buildData, setBuildData] = useState(null);
  const [submitData, setSubmitData] = useState(null);
  const [error, setError] = useState(null);
  const [payloadView, setPayloadView] = useState("hex"); // "hex" | "readable"
  const [overrideValue, setOverrideValue] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/scenarios`)
      .then(async (r) => {
        await throwForStatus(r);
        return r.json();
      })
      .then(setScenarios)
      .catch((e) => setError(`Could not load scenarios: ${e.message}`));
  }, []);

  const selected = Array.isArray(scenarios) ? scenarios.find((s) => s.id === selectedId) : undefined;

  function selectScenario(id) {
    setSelectedId(id);
    setView("scenario");
    setStage("selected");
    setBuildData(null);
    setSubmitData(null);
    setError(null);
    setPayloadView("hex");
    setOverrideValue("");
  }

  function goHome() {
    setView("home");
  }

  async function doBuild(overrideSats) {
    const isRebuild = overrideSats !== undefined;
    setStage(isRebuild ? "built" : "building");
    setError(null);
    if (isRebuild) setSubmitData(null);
    try {
      const body = { scenario_id: selectedId };
      if (isRebuild) body.override_value_sats = overrideSats;
      const res = await fetch(`${API_BASE}/build`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      await throwForStatus(res);
      const data = await res.json();
      setBuildData(data);
      if (data.editable_value !== undefined && data.editable_value !== null) {
        setOverrideValue(String(data.editable_value));
      }
      setStage("built");
    } catch (e) {
      setError(`${isRebuild ? "Rebuild" : "Build"} failed: ${e.message}`);
      setStage(isRebuild ? "built" : "selected");
    }
  }

  async function doSubmit() {
    setStage("submitting");
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ build_id: buildData.build_id }),
      });
      await throwForStatus(res);
      const data = await res.json();
      setSubmitData(data);
      setStage("response");
    } catch (e) {
      setError(`Submit failed: ${e.message}`);
      setStage("built");
    }
  }

  return (
    <div className="app">
      <div className="topbar">
        <h1 className="app-title-link" onClick={goHome}>
          My BTC Playground
        </h1>
        <span className="subtitle">break Bitcoin's consensus rules on purpose</span>
        <div className="topbar-spacer" />
        <NodeStatus />
      </div>
      <div className="layout">
        <div className="sidebar">
          <button className={`nav-home ${view === "home" ? "active" : ""}`} onClick={goHome}>
            Home
          </button>
          <div className="sidebar-label">Scenarios</div>
          {scenarios.map((s) => (
            <button
              key={s.id}
              className={`scenario-btn ${view === "scenario" && s.id === selectedId ? "active" : ""}`}
              onClick={() => selectScenario(s.id)}
            >
              <span className="title">{s.title}</span>
              <span className="kind">{s.kind}</span>
            </button>
          ))}
        </div>
        <div className="main">
          {error && <div className="error-banner">{error}</div>}

          {view === "home" && <HomePage scenarios={scenarios} onSelectScenario={selectScenario} />}

          {view === "scenario" && !selected && !error && (
            <p className="empty-state">
              Pick an attack on the left. Nothing happens automatically -- each step below is a
              real request to a live regtest Bitcoin Core node, and you trigger it.
            </p>
          )}

          {view === "scenario" && selected && (
            <>
              <div className="scenario-header">
                <h2>{selected.title}</h2>
                <p className="explanation">{selected.explanation}</p>
              </div>

              <StepTracker stage={stage} />

              <div className="panes">
                {/* Step 1: Build */}
                <div className="pane">
                  <div className="pane-header">
                    <span>1. The Payload</span>
                    {stage === "selected" && (
                      <button className="action-btn" onClick={() => doBuild()}>
                        Build Payload
                      </button>
                    )}
                    {buildData && (
                      <div className="view-toggle">
                        <button
                          className={`view-toggle-btn ${payloadView === "hex" ? "active" : ""}`}
                          onClick={() => setPayloadView("hex")}
                        >
                          Hex
                        </button>
                        <button
                          className={`view-toggle-btn ${payloadView === "readable" ? "active" : ""}`}
                          onClick={() => setPayloadView("readable")}
                        >
                          Readable
                        </button>
                      </div>
                    )}
                  </div>
                  <div className="pane-body">
                    {stage === "selected" && (
                      <p className="step-hint">
                        Click "Build Payload" to construct this attack server-side, against the
                        live node's current chain tip.
                      </p>
                    )}
                    {stage === "building" && <p className="loading">Constructing payload on the node&hellip;</p>}
                    {buildData && (
                      <>
                        {payloadView === "hex" ? (
                          buildData.baseline_hex ? (
                            <HexDiff baselineHex={buildData.baseline_hex} payloadHex={buildData.payload_hex} />
                          ) : (
                            <pre className="payload-hex">{buildData.payload_hex}</pre>
                          )
                        ) : (
                          <DecodedView structured={buildData.payload_structured} />
                        )}
                        <div className="build-calls">
                          <span className="build-calls-label">RPC calls used to build this:</span>{" "}
                          {buildData.build_calls.map((c, i) => (
                            <code key={i} className="rpc-chip">
                              {c}
                            </code>
                          ))}
                        </div>
                        {buildData.baseline_hex && (
                          <p className="step-hint diff-hint">
                            <span className="hex-diff-swatch" /> highlighted{" "}
                            {payloadView === "hex" ? "bytes" : "fields"} differ from a valid baseline
                          </p>
                        )}
                      </>
                    )}
                  </div>
                </div>

                {/* Optional: tune the one field this scenario exposes */}
                {selected.editable && buildData && (
                  <div className="pane pane-editable">
                    <div className="pane-header">Try a different value</div>
                    <div className="pane-body">
                      <p className="step-hint">
                        Subsidy at this height is{" "}
                        <strong>{buildData.subsidy_sats?.toLocaleString()} sats</strong>. Pick any{" "}
                        {selected.editable.label.toLowerCase()} and rebuild -- watch the verdict flip
                        right at the boundary.
                      </p>
                      <div className="editable-row">
                        <input
                          type="number"
                          className="editable-input"
                          min={selected.editable.min}
                          max={selected.editable.max}
                          step={selected.editable.step}
                          value={overrideValue}
                          onChange={(e) => setOverrideValue(e.target.value)}
                        />
                        <button
                          className="action-btn"
                          onClick={() => doBuild(Number(overrideValue))}
                          disabled={overrideValue === ""}
                        >
                          Rebuild
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Step 2: Submit */}
                {stage === "built" && (
                  <div className="pane pane-action">
                    <div className="pane-body pane-body-center">
                      <p className="step-hint">
                        Ready to submit this exact payload to <code>bitcoind</code> for real validation.
                      </p>
                      <button className="action-btn action-btn-primary" onClick={doSubmit}>
                        Submit to Node &rarr;
                      </button>
                    </div>
                  </div>
                )}
                {stage === "submitting" && (
                  <div className="pane pane-action">
                    <div className="pane-body pane-body-center">
                      <p className="loading">Submitting to node&hellip;</p>
                    </div>
                  </div>
                )}

                {/* Step 3: Request + raw Response */}
                {submitData && (
                  <>
                    <div className="pane">
                      <div className="pane-header">2. The Request (JSON-RPC)</div>
                      <div className="pane-body">
                        <pre className="json-block">
                          {`bitcoin-cli -regtest ${submitData.rpc_request.method} '${JSON.stringify(
                            submitData.rpc_request.params
                          )}'`}
                        </pre>
                      </div>
                    </div>

                    <div className="pane">
                      <div className="pane-header">
                        <span>3. The Raw Response</span>
                        <span className="elapsed-badge">{submitData.elapsed_ms}ms round trip</span>
                      </div>
                      <div className="pane-body">
                        <pre className="json-block">{JSON.stringify(submitData.rpc_response, null, 2)}</pre>
                        {stage === "response" && (
                          <button className="action-btn action-btn-primary reveal-btn" onClick={() => setStage("revealed")}>
                            Reveal Verdict &amp; Source &rarr;
                          </button>
                        )}
                      </div>
                    </div>
                  </>
                )}

                {/* Step 4: Verdict + Source */}
                {stage === "revealed" && (
                  <>
                    <div className="pane verdict">
                      <div className="pane-header">4. The Verdict</div>
                      <div className="pane-body">
                        <div className={`verdict-string ${submitData.accepted ? "accepted" : "rejected"}`}>
                          {submitData.accepted ? "accepted" : submitData.verdict}
                        </div>
                        <RuleTypeBadge ruleType={submitData.rule_type} />
                      </div>
                    </div>

                    <div className="pane">
                      <div className="pane-header">The Source</div>
                      <div className="pane-body">
                        {submitData.source ? (
                          <>
                            <div className="source-location">
                              <strong>{submitData.source.file}</strong> &middot; {submitData.source.function} &middot; lines{" "}
                              {submitData.source.lines[0]}-{submitData.source.lines[1]}
                              <br />
                              <a href={submitData.source.permalink} target="_blank" rel="noreferrer">
                                view on GitHub &rarr;
                              </a>
                            </div>
                            <pre className="source-snippet">{submitData.source.snippet}</pre>
                          </>
                        ) : (
                          <p className="source-empty">No mapped source location for this verdict.</p>
                        )}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
