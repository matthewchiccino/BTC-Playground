const REPO_SHA = "0574c95b1637f4ef7df19d3d665cacb39f61de91";
const REPO_BLOB = (path) => `https://github.com/matthewchiccino/BTC-Playground/blob/${REPO_SHA}/${path}`;
const CORE_COMMIT = "9be056a8a72b624dae9623b2f7bded92c2a21c91";
const CORE_PERMALINK = (path, a, b) =>
  `https://github.com/bitcoin/bitcoin/blob/${CORE_COMMIT}/${path}#L${a}-L${b}`;

export default function AboutApproach() {
  return (
    <div className="home-page">
      <div className="home-eyebrow">About</div>
      <h2>The Source Map</h2>
      <p className="home-lede">
        Every verdict in this app links to the exact line of C++ that produced it. Here's how that
        actually got built, warts included.
      </p>

      <p className="home-copy">
        <a href="https://github.com/bitcoin/bitcoin" target="_blank" rel="noreferrer">
          bitcoin/bitcoin
        </a>{" "}
        is a real, actively-developed C++ codebase -- hundreds of thousands of lines, decades of
        history, dozens of contributors. The rejection strings this app shows (<code>dust</code>,{" "}
        <code>bad-cb-amount</code>, and so on) live inside a handful of its files:{" "}
        <code>src/validation.cpp</code>, <code>src/consensus/tx_verify.cpp</code>,{" "}
        <code>src/policy/policy.cpp</code>. Every permalink in this app points at one specific
        commit --{" "}
        <a href={`https://github.com/bitcoin/bitcoin/tree/${CORE_COMMIT}`} target="_blank" rel="noreferrer">
          {CORE_COMMIT.slice(0, 10)}
        </a>{" "}
        (tag v31.1) -- never a branch name. Line numbers on a moving branch drift within weeks;
        pin to a SHA and a permalink stays correct forever.
      </p>

      <h3 className="home-subhead">It started fully manual</h3>
      <p className="home-copy">
        For every scenario: build the attack, run it against the live node, read the real
        verdict, then go find the C++ that produced it. Not "this is probably the check" from
        memory or docs -- the actual node's actual output, then the actual source, every time.
        That discipline caught real, non-obvious things a docs page would never have surfaced:
      </p>
      <ul className="home-steps">
        <li>
          <strong>Missing inputs vs. already spent.</strong> <code>testmempoolaccept</code> can't
          tell "this UTXO never existed" apart from "this UTXO was already spent" -- both just
          report <code>missing-inputs</code>. The real{" "}
          <code>bad-txns-inputs-missingorspent</code> string only appears in{" "}
          <em>block-context</em> validation, which is why Double Spend proposes a block instead of
          just checking the mempool.
        </li>
        <li>
          <strong>The same string, two different reasons.</strong> Dust Output's verdict is{" "}
          <code>"dust"</code> -- but that string is emitted from two entirely different files, for
          two entirely different reasons (one tolerates a single dust output if the transaction is
          completely fee-free; the other counts dust outputs outright). Reading either file in
          isolation gives a plausible-looking wrong answer. Only running the actual payload against
          the actual node revealed which one was really firing.
        </li>
      </ul>

      <h3 className="home-subhead">Then it got automated</h3>
      <p className="home-copy">
        Six hand-verified entries is manageable. But hand-verification is exactly how the dust
        mix-up above happened in the first place -- it's easy to find <em>a</em> plausible call
        site and stop looking, without knowing there's a second one. And every time this project
        re-pins to a newer Core release, every line number needs re-checking by hand, or it quietly
        rots.
      </p>
      <p className="home-copy">
        <code>gen_sources.py</code> fixes both problems at once: it walks Core's actual source tree
        at the pinned commit -- via GitHub's API and raw file fetches, no local clone, no compiled
        build -- and finds <em>every</em> call site that can produce a given rejection string, not
        just the first one someone happened to grep into existence. A full scan across all 1,380 of
        Core's <code>src/</code> files takes about a minute.
      </p>

      <pre className="json-block">{`INVALID_CALL_RE = re.compile(
    r"\\.Invalid\\(\\s*[\\w:]+::\\w+\\s*,\\s*"
    r'(?:"((?:[^"\\\\]|\\\\.)*)"'
    r'|strprintf\\(\\s*"((?:[^"\\\\]|\\\\.)*)")'
)
REASON_ASSIGN_RE = re.compile(r'\\breason\\s*=\\s*"((?:[^"\\\\]|\\\\.)*)"\\s*;')`}</pre>
      <p className="home-copy diff-hint">
        Two different idioms Core actually uses for rejecting something -- a{" "}
        <code>state.Invalid(...)</code> call, and a plain <code>reason = "...";</code> assignment
        used only in <code>policy.cpp</code>. A regex tuned for one silently misses the other.
      </p>

      <p className="home-copy">
        Running it against the six scenarios already in this app confirmed both known ambiguities
        as real (not scanner noise) and found nothing else silently wrong in the other four --
        which is exactly the point: the tool doesn't replace checking against the live node, it
        scales the part that hand-verification is bad at.
      </p>

      <h3 className="home-subhead">The actual files</h3>
      <div className="fixture-table">
        <div className="fixture-row">
          <div className="fixture-name">
            <a href={REPO_BLOB("backend/sources.py")} target="_blank" rel="noreferrer">
              backend/sources.py
            </a>
          </div>
          <p className="source-also-note">
            The hand-maintained catalog itself -- rejection string to {"{"}file, function, lines,
            permalink, snippet{"}"}, with an optional <code>also_produced_by</code> when a string
            genuinely has more than one real source.
          </p>
        </div>
        <div className="fixture-row">
          <div className="fixture-name">
            <a href={REPO_BLOB("backend/gen_sources.py")} target="_blank" rel="noreferrer">
              backend/gen_sources.py
            </a>
          </div>
          <p className="source-also-note">
            The scanner: <code>scan</code> walks Core's source tree and writes every candidate;{" "}
            <code>diff</code> compares that against the committed catalog and reports what moved,
            vanished, or turned out ambiguous.
          </p>
        </div>
        <div className="fixture-row">
          <div className="fixture-name">
            <a href={REPO_BLOB("backend/test_sources.py")} target="_blank" rel="noreferrer">
              backend/test_sources.py
            </a>
          </div>
          <p className="source-also-note">
            A standing pytest check, independent of re-pinning: for every committed entry, fetch
            its file at the pinned commit and assert the literal string is actually still there at
            the declared lines. Catches a bad hand-edit immediately instead of it sitting there
            confidently wrong.
          </p>
        </div>
      </div>

      <h3 className="home-subhead">Why two layers, not one</h3>
      <p className="home-copy">
        Empirical verification (run it, read the real answer) and static scanning (read the actual
        source tree) catch different failure modes. The live node tells you what actually happens
        for a specific payload, right now, but says nothing about whether some other input would
        hit a different check. The source scan finds every possible call site, but can't tell you
        which one fires without running something. Neither one alone would have caught the dust bug
        cleanly -- the live node found <em>that</em> something was off, the source scan explained{" "}
        <em>why</em>, with a permalink to prove it.
      </p>
    </div>
  );
}
