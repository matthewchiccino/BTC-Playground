"""Hand-mapped table: verbatim rejection string -> the C++ check that produced it.

Every entry here was found and verified by hand against the actual bitcoind
running in this project (v31.1), by triggering the scenario and reading the
verdict. Pinned to a commit SHA, not a branch, so line numbers never drift
out from under the permalink. See vendor/VENDORED.md for the pinned commit.
"""

COMMIT = "9be056a8a72b624dae9623b2f7bded92c2a21c91"


def _permalink(file: str, start: int, end: int) -> str:
    return f"https://github.com/bitcoin/bitcoin/blob/{COMMIT}/{file}#L{start}-L{end}"


SOURCES = {
    "bad-cb-amount": {
        "file": "src/validation.cpp",
        "function": "Chainstate::ConnectBlock",
        "lines": [2613, 2616],
        "permalink": _permalink("src/validation.cpp", 2613, 2616),
        "snippet": (
            "CAmount blockReward = nFees + GetBlockSubsidy(pindex->nHeight, params.GetConsensus());\n"
            "if (block.vtx[0]->GetValueOut() > blockReward && state.IsValid()) {\n"
            '    state.Invalid(BlockValidationResult::BLOCK_CONSENSUS, "bad-cb-amount",\n'
            '                  strprintf("coinbase pays too much (actual=%d vs limit=%d)", block.vtx[0]->GetValueOut(), blockReward));'
        ),
        "rule_type": "consensus",
    },
    "bad-txnmrklroot": {
        "file": "src/validation.cpp",
        "function": "CheckMerkleRoot",
        "lines": [3885, 3895],
        "permalink": _permalink("src/validation.cpp", 3885, 3895),
        "snippet": (
            "static bool CheckMerkleRoot(const CBlock& block, BlockValidationState& state)\n"
            "{\n"
            "    if (block.m_checked_merkle_root) return true;\n"
            "\n"
            "    bool mutated;\n"
            "    uint256 merkle_root = BlockMerkleRoot(block, &mutated);\n"
            "    if (block.hashMerkleRoot != merkle_root) {\n"
            "        return state.Invalid(\n"
            "            /*result=*/BlockValidationResult::BLOCK_MUTATED,\n"
            '            /*reject_reason=*/"bad-txnmrklroot",\n'
            '            /*debug_message=*/"hashMerkleRoot mismatch");'
        ),
        "rule_type": "consensus",
    },
    "bad-txns-inputs-missingorspent": {
        "file": "src/consensus/tx_verify.cpp",
        "function": "Consensus::CheckTxInputs",
        "lines": [164, 170],
        "permalink": _permalink("src/consensus/tx_verify.cpp", 164, 170),
        "snippet": (
            "bool Consensus::CheckTxInputs(const CTransaction& tx, TxValidationState& state, const CCoinsViewCache& inputs, int nSpendHeight, CAmount& txfee)\n"
            "{\n"
            "    // are the actual inputs available?\n"
            "    if (!inputs.HaveInputs(tx)) {\n"
            '        return state.Invalid(TxValidationResult::TX_MISSING_INPUTS, "bad-txns-inputs-missingorspent",\n'
            '                         strprintf("%s: inputs missing/spent", __func__));\n'
            "    }"
        ),
        "rule_type": "consensus",
    },
    "dust": {
        # Found wrong at first: this originally cited IsStandardTx (below,
        # in also_produced_by), which only fires when a tx has >1 dust
        # outputs. dust_output() builds a tx with exactly ONE dust output
        # plus a nonzero fee -- PreCheckEphemeralTx is what actually fires,
        # and it runs earlier in MemPoolAccept's check sequence. Confirmed
        # by gen_sources.py's scan (both are real call sites for "dust")
        # plus the live node (this is genuinely which one returns for our
        # payload).
        "file": "src/policy/ephemeral_policy.cpp",
        "function": "PreCheckEphemeralTx",
        "lines": [23, 27],
        "permalink": _permalink("src/policy/ephemeral_policy.cpp", 23, 27),
        "snippet": (
            "bool PreCheckEphemeralTx(const CTransaction& tx, CFeeRate dust_relay_rate, CAmount base_fee, CAmount mod_fee, TxValidationState& state)\n"
            "{\n"
            "    // We never want to give incentives to mine this transaction alone\n"
            "    if ((base_fee != 0 || mod_fee != 0) && !GetDust(tx, dust_relay_rate).empty()) {\n"
            '        return state.Invalid(TxValidationResult::TX_NOT_STANDARD, "dust", "tx with dust output must be 0-fee");'
        ),
        "rule_type": "policy",
        "also_produced_by": [
            {
                "file": "src/policy/policy.cpp",
                "function": "IsStandardTx",
                "lines": [157, 160],
                "permalink": _permalink("src/policy/policy.cpp", 157, 160),
                "note": (
                    "Same string, different check: this only fires when a tx has "
                    "MORE THAN ONE dust output. This scenario's tx has exactly "
                    "one dust output plus a nonzero fee, so IsStandardTx's own "
                    "count > 1 condition is false here -- PreCheckEphemeralTx "
                    "(the primary entry) is what actually fires first."
                ),
            }
        ],
    },
    "min relay fee not met": {
        "file": "src/validation.cpp",
        "function": "MemPoolAccept::CheckFeeRate",
        "lines": [714, 717],
        "permalink": _permalink("src/validation.cpp", 714, 717),
        "snippet": (
            "if (package_fee < m_pool.m_opts.min_relay_feerate.GetFee(package_size)) {\n"
            '    return state.Invalid(TxValidationResult::TX_RECONSIDERABLE, "min relay fee not met",\n'
            "                         strprintf(\"%d < %d\", package_fee, m_pool.m_opts.min_relay_feerate.GetFee(package_size)));\n"
            "}"
        ),
        "rule_type": "policy",
    },
    "bad-txns-premature-spend-of-coinbase": {
        "file": "src/consensus/tx_verify.cpp",
        "function": "Consensus::CheckTxInputs",
        "lines": [178, 181],
        "permalink": _permalink("src/consensus/tx_verify.cpp", 178, 181),
        "snippet": (
            "// If prev is coinbase, check that it's matured\n"
            "if (coin.IsCoinBase() && nSpendHeight - coin.nHeight < COINBASE_MATURITY) {\n"
            '    return state.Invalid(TxValidationResult::TX_PREMATURE_SPEND, "bad-txns-premature-spend-of-coinbase",\n'
            "        strprintf(\"tried to spend coinbase at depth %d\", nSpendHeight - coin.nHeight));\n"
            "}"
        ),
        "rule_type": "consensus",
    },
}
