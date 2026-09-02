const REPO_SHA = "0574c95b1637f4ef7df19d3d665cacb39f61de91";
const REPO_BLOB = (path) => `https://github.com/matthewchiccino/BTC-Playground/blob/${REPO_SHA}/${path}`;
const CORE_COMMIT = "9be056a8a72b624dae9623b2f7bded92c2a21c91";

export default function AboutApproach() {
  return (
    <div className="home-page">
      <div className="home-eyebrow">About</div>
      <h2>The Source Map</h2>
      <p className="home-lede">
        Every verdict in this app links to the exact line of C++ that produced it. Here's how it
        works.
      </p>

      <h3 className="home-subhead">Why</h3>
      <p className="home-copy">
        The source code for Bitcoin, called Bitcoin Core, lives at{" "}
        <a href="https://github.com/bitcoin/bitcoin" target="_blank" rel="noreferrer">
          bitcoin/bitcoin
        </a>{" "}
        . It contains hundreds of thousands of lines of C++ code. We are running an instance
        of this program, a bitcoin core node, inside this sandbox. The responses you see come directly
        from the nodes actual code. It will point the exact line of code that produced the response. 
        
        It's not an intuitive process, and its easy to get wrong. The same string can come from two 
        different checks for two different reasons, so the source map built for this app is a 
        comprehensive list of all the places a given string can come from, and an explination of 
        where percicely that response came from.

      </p>

      <h3 className="home-subhead">How</h3>
      <p className="home-copy">
        Every citation started the same way: build the attack, run it against the live node, read
        the real verdict, then go find that exact check in the source. Not a guess from memory,
        the node's real answer, then the real code.
      </p>
      <p className="home-copy">
        Every permalink points at one specific commit: {" "}
        <a href={`https://github.com/bitcoin/bitcoin/tree/${CORE_COMMIT}`} target="_blank" rel="noreferrer">
          {CORE_COMMIT.slice(0, 10)}
        </a>{" "}
        (tag v31.1). Line numbers on a moving branch drift within weeks. If we instead pin
        to a commit, our reference stays permanently correct. 
      </p>
      <p className="home-copy">
        To catch the "same string, two checks" problem, our script<code>gen_sources.py</code> scans Core's
        actual source tree and finds every place a given rejection string could come from, not
        just the first one someone happened to find. <code>test_sources.py</code> then checks
        every citation against the real file, so a bad one gets caught right away instead of
        sitting there quietly wrong.
      </p>

      <pre className="json-block">{`INVALID_CALL_RE = re.compile(
    r"\\.Invalid\\(\\s*[\\w:]+::\\w+\\s*,\\s*"
    r'(?:"((?:[^"\\\\]|\\\\.)*)"'
    r'|strprintf\\(\\s*"((?:[^"\\\\]|\\\\.)*)")'
)
REASON_ASSIGN_RE = re.compile(r'\\breason\\s*=\\s*"((?:[^"\\\\]|\\\\.)*)"\\s*;')`}</pre>
      <p className="home-copy diff-hint">
        The actual regex from <code>gen_sources.py</code>. Two patterns because Core rejects
        things two different ways: a <code>state.Invalid(...)</code> call, and a plain{" "}
        <code>reason = "...";</code> assignment used only in <code>policy.cpp</code>.
      </p>

      <h3 className="home-subhead">The files</h3>
      <div className="fixture-table">
        <div className="fixture-row">
          <div className="fixture-name">
            <a href={REPO_BLOB("backend/sources.py")} target="_blank" rel="noreferrer">
              backend/sources.py
            </a>
          </div>
          <p className="source-also-note">
            The catalog itself -- rejection string to {"{"}file, function, lines, permalink,
            snippet{"}"}.
          </p>
        </div>
        <div className="fixture-row">
          <div className="fixture-name">
            <a href={REPO_BLOB("backend/gen_sources.py")} target="_blank" rel="noreferrer">
              backend/gen_sources.py
            </a>
          </div>
          <p className="source-also-note">
            Scans Core's source tree and writes every candidate; diffs that against the catalog.
          </p>
        </div>
        <div className="fixture-row">
          <div className="fixture-name">
            <a href={REPO_BLOB("backend/test_sources.py")} target="_blank" rel="noreferrer">
              backend/test_sources.py
            </a>
          </div>
          <p className="source-also-note">
            Checks every catalog entry against the real file at the pinned commit.
          </p>
        </div>
      </div>
    </div>
  );
}
