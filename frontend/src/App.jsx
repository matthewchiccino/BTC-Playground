import { useEffect, useState } from "react";
import "./App.css";
import AboutApproach from "./AboutApproach";
import AboutNode from "./AboutNode";
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

function Explanation({ text, reference }) {
  if (!reference) return <p className="explanation">{text}</p>;
  const [before, after] = text.split("{ref}");
  return (
    <p className="explanation">
      {before}
      <a href={reference.url} target="_blank" rel="noreferrer" className="inline-ref-link">
        {reference.label}
      </a>
      {after}
    </p>
  );
}

export default function App() {
  const [scenarios, setScenarios] = useState([]);
  const [view, setView] = useState("home"); // "home" | "scenario" | "about-node" | "about-approach"
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

  function goAbout(page) {
    setView(page); // "about-node" | "about-approach"
  }

  async function doBuild(overrideVal) {
    const isRebuild = overrideVal !== undefined;
    setStage(isRebuild ? "built" : "building");
    setError(null);
    if (isRebuild) setSubmitData(null);
    try {
      const body = { scenario_id: selectedId };
      if (isRebuild) {
        const type = selected.editable.type;
        if (type === "int") body.override_value_sats = Number(overrideVal);
        else if (type === "hex") body.override_hex = overrideVal;
        else if (type === "choice") body.override_choice = overrideVal;
      }
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
          BTC Playground
        </h1>
        <span className="subtitle">break Bitcoin's consensus rules on purpose</span>
        <div className="topbar-spacer" />
        <NodeStatus />
      </div>
      <div className="layout">
        <div className="sidebar">
          <div className="sidebar-label">About</div>
          <button className={`nav-home ${view === "home" ? "active" : ""}`} onClick={goHome}>
            Home
          </button>
          <button
            className={`nav-home ${view === "about-node" ? "active" : ""}`}
            onClick={() => goAbout("about-node")}
          >
            The Node
          </button>
          <button
            className={`nav-home ${view === "about-approach" ? "active" : ""}`}
            onClick={() => goAbout("about-approach")}
          >
            The Source Map
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
          {view === "about-node" && <AboutNode />}
          {view === "about-approach" && <AboutApproach />}

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
                <Explanation text={selected.explanation} reference={selected.reference} />
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
                        {buildData.baseline_hex && (
                          <p className="step-hint diff-hint">
                            <span className="hex-diff-swatch" /> highlighted{" "}
                            {payloadView === "hex" ? "bytes" : "fields"} differ from a valid baseline
                          </p>
                        )}
                        {selected.editable && (
                          <div className="editable-inline">
                            {selected.editable.type === "int" && selected.id === "coinbase_oversubsidy" && (
                              <p className="step-hint">
                                Subsidy at this height is{" "}
                                <strong>{buildData.subsidy_sats?.toLocaleString()} sats</strong>. Pick a new
                                payout and rebuild -- watch the verdict flip.
                              </p>
                            )}
                            {selected.editable.type === "int" && selected.id === "dust_output" && (
                              <p className="step-hint">
                                The dust threshold is{" "}
                                <strong>{buildData.hint_value?.toLocaleString()} sats</strong>. This tx
                                pays an ordinary fee, so it can't carry a dust output at all. Pick a
                                value and rebuild to watch the verdict flip right at the line.
                              </p>
                            )}
                            {selected.editable.type === "int" && selected.id === "fee_too_low" && (
                              <p className="step-hint">
                                This transaction needs at least{" "}
                                <strong>{buildData.hint_value?.toLocaleString()} sats</strong> to clear
                                this node's relay floor, given its size. Pick a fee and rebuild to
                                watch the verdict flip right at the line.
                              </p>
                            )}
                            {selected.editable.type === "int" && selected.id === "coinbase_maturity" && (
                              <p className="step-hint">
                                A coinbase reward needs{" "}
                                <strong>{buildData.hint_value} confirmations</strong> before it's
                                spendable. Pick a confirmation count and rebuild to watch the verdict
                                flip right at the line.
                              </p>
                            )}
                            {selected.editable.type === "hex" && (
                              <p className="step-hint">
                                Every node recomputes this from scratch. Only one exact value is
                                accepted -- everything else, even a single flipped character, is
                                rejected. The correct value is <code>{buildData.hint_value}</code>.
                              </p>
                            )}
                            {selected.editable.type === "choice" && (
                              <p className="step-hint">
                                One of these is genuinely still spendable, one was already spent in this
                                chain. Pick either and rebuild to compare.
                              </p>
                            )}
                            <div className="editable-row">
                              {selected.editable.type === "choice" ? (
                                <select
                                  className="editable-input editable-input-medium"
                                  value={overrideValue}
                                  onChange={(e) => setOverrideValue(e.target.value)}
                                >
                                  {selected.editable.options.map((o) => (
                                    <option key={o.value} value={o.value}>
                                      {o.label}
                                    </option>
                                  ))}
                                </select>
                              ) : (
                                <input
                                  type={selected.editable.type === "hex" ? "text" : "number"}
                                  className={`editable-input ${selected.editable.type === "int" ? "editable-input-narrow" : ""}`}
                                  min={selected.editable.min}
                                  max={selected.editable.max}
                                  step={selected.editable.step}
                                  maxLength={selected.editable.length}
                                  spellCheck={false}
                                  value={overrideValue}
                                  onChange={(e) => setOverrideValue(e.target.value)}
                                />
                              )}
                              <button
                                className="action-btn"
                                onClick={() => doBuild(overrideValue)}
                                disabled={overrideValue === ""}
                              >
                                Rebuild
                              </button>
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>

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
                            {submitData.source.also_produced_by?.length > 0 && (
                              <details className="source-also">
                                <summary>
                                  Also produced by {submitData.source.also_produced_by.length} other site(s)
                                </summary>
                                {submitData.source.also_produced_by.map((alt) => (
                                  <div className="source-also-item" key={alt.permalink}>
                                    <div className="source-location">
                                      <strong>{alt.file}</strong> &middot; {alt.function} &middot; lines{" "}
                                      {alt.lines[0]}-{alt.lines[1]}
                                      <br />
                                      <a href={alt.permalink} target="_blank" rel="noreferrer">
                                        view on GitHub &rarr;
                                      </a>
                                    </div>
                                    <p className="source-also-note">{alt.note}</p>
                                  </div>
                                ))}
                              </details>
                            )}
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
