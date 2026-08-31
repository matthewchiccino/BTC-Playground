export default function HomePage({ scenarios, onSelectScenario }) {
  return (
    <div className="home-page">
      <div className="home-eyebrow">Home</div>
      <h2>My BTC Playground</h2>
      <p className="home-lede">Break Bitcoin's consensus rules on purpose.</p>

      <p className="home-copy">
        Bitcoin Core constatnly rejects invalid blocks and transactions. By learning seeing how and why,
        we can understand the bitcoin protocal much better from a operational and implementational level.
        This is an interactive sandbox that builds deliberately invalid attacks and submits them to a 
        real live regtest Bitcoin Core node, so you can see exactly which line of code catches it.
      </p>
      <p className="home-copy">
        Nothing here is simulated. Every scenario runs against a real <code>bitcoind</code> process
        using read-only RPC calls so nothing is ever actually broadcast or mined. The chain is 
        frozen; state never changes, which is what lets everyone share one node safely.
      </p>

      <h3 className="home-subhead">How to use it</h3>
      <ol className="home-steps">
        <li>
          <strong>Build</strong>: construct the attack payload server-side, against the live
          chain tip.
        </li>
        <li>
          <strong>Submit</strong>: send that exact payload to the node for real validation.
        </li>
        <li>
          <strong>Response</strong>: see the raw JSON-RPC exchange and how long it actually took.
        </li>
        <li>
          <strong>Verdict</strong>: the node's verbatim rejection string, plus the C++ source
          line that produced it.
        </li>
      </ol>
      <p className="home-copy">
        At step 1 you can toggle between the raw hex and a readable, field-by-field decoded view
        whichever's changed from a valid baseline is always highlighted.
      </p>

      <h3 className="home-subhead">Scenarios</h3>
      <div className="home-scenario-list">
        {scenarios.map((s) => (
          <button key={s.id} className="home-scenario-card" onClick={() => onSelectScenario(s.id)}>
            <div className="home-scenario-card-head">
              <span className="title">{s.title}</span>
              <span className="kind">{s.kind}</span>
            </div>
            <p>{s.explanation}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
