// Byte-level diff between two same-length hex strings. Highlights the exact
// bytes the mutation changed, so "one satoshi" or "one bit" is visible, not
// just asserted.
export default function HexDiff({ baselineHex, payloadHex }) {
  if (!baselineHex || baselineHex.length !== payloadHex.length) {
    return <pre className="payload-hex">{payloadHex}</pre>;
  }

  const spans = [];
  for (let i = 0; i < payloadHex.length; i += 2) {
    const a = baselineHex.slice(i, i + 2);
    const b = payloadHex.slice(i, i + 2);
    spans.push(
      <span key={i} className={a === b ? undefined : "hex-diff-byte"}>
        {b}
      </span>
    );
  }

  return <pre className="payload-hex">{spans}</pre>;
}
