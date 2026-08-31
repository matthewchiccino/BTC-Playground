// Readable rendering of payload_structured. Mirrors HexDiff's highlighting:
// any field the backend flagged as "changed" (relative to a valid baseline)
// gets the same accent highlight, just at field granularity instead of byte.
function Field({ label, field }) {
  if (!field) return null;
  return (
    <div className="decoded-row">
      <span className="decoded-label">{label}</span>
      <span className={`decoded-value ${field.changed ? "field-changed" : ""}`}>{String(field.value)}</span>
    </div>
  );
}

function formatSats(field) {
  return { ...field, value: `${field.value.toLocaleString()} sats` };
}

export default function DecodedView({ structured }) {
  if (!structured) return null;
  const { header, transactions } = structured;

  return (
    <div className="decoded-view">
      {header && (
        <div className="decoded-section">
          <div className="decoded-section-title">Block Header</div>
          <Field label="version" field={header.version} />
          <Field label="prev block" field={header.prev_block_hash} />
          <Field label="merkle root" field={header.merkle_root} />
          <Field label="time" field={header.time} />
          <Field label="bits" field={header.bits} />
          <Field label="nonce" field={header.nonce} />
        </div>
      )}
      {transactions.map((tx, i) => (
        <div className="decoded-section" key={i}>
          <div className="decoded-section-title">{i === 0 && header ? "Coinbase Transaction" : `Transaction ${i}`}</div>
          <Field label="txid" field={tx.txid} />
          <Field label="version" field={tx.version} />
          <Field label="locktime" field={tx.locktime} />
          {tx.vin.map((vin, vi) => (
            <div className="decoded-subsection" key={`in-${vi}`}>
              <div className="decoded-subsection-title">Input {vi}</div>
              <Field label="prev txid" field={vin.prev_txid} />
              <Field label="prev vout" field={vin.prev_vout} />
              <Field label="scriptSig (asm)" field={vin.scriptSig_asm} />
              <Field label="sequence" field={vin.sequence} />
            </div>
          ))}
          {tx.vout.map((vout, vo) => (
            <div className="decoded-subsection" key={`out-${vo}`}>
              <div className="decoded-subsection-title">Output {vo}</div>
              <Field label="value" field={formatSats(vout.value_sats)} />
              <Field label="scriptPubKey (asm)" field={vout.scriptPubKey_asm} />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
