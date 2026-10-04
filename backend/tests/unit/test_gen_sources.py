"""The scanner's function-boundary heuristic is not a C++ parser (its own
docstring says so), which is exactly why it needs tests: these pin down the
two code shapes Core actually uses, using verbatim snippets from sources.py.
"""
from gen_sources import _clean_prefix, find_enclosing_function, scan_file


def lines_of(text: str) -> list[str]:
    return text.strip("\n").splitlines()


ALLMAN = lines_of('''
bool Consensus::CheckTxInputs(const CTransaction& tx, TxValidationState& state)
{
    // are the actual inputs available?
    if (!inputs.HaveInputs(tx)) {
        return state.Invalid(TxValidationResult::TX_MISSING_INPUTS, "bad-txns-inputs-missingorspent",
                         strprintf("%s: inputs missing/spent", __func__));
    }
}
''')

NESTED_KNR = lines_of('''
static bool ContextualCheckBlock(const CBlock& block, BlockValidationState& state)
{
    for (const auto& tx : block.vtx) {
        if (!IsFinalTx(*tx, nHeight, nLockTimeCutoff)) {
            return state.Invalid(BlockValidationResult::BLOCK_CONSENSUS, "bad-txns-nonfinal", "non-final transaction");
        }
    }
}
''')


def test_finds_function_through_allman_braces_and_an_if():
    hit = next(i for i, l in enumerate(ALLMAN) if ".Invalid(" in l)
    assert find_enclosing_function(ALLMAN, hit) == "Consensus::CheckTxInputs"


def test_skips_for_and_if_blocks_to_reach_the_function():
    hit = next(i for i, l in enumerate(NESTED_KNR) if ".Invalid(" in l)
    assert find_enclosing_function(NESTED_KNR, hit) == "ContextualCheckBlock"


def test_returns_unknown_when_there_is_no_enclosing_function():
    assert find_enclosing_function(lines_of("int x = 1;\nint y = 2;"), 1) == "<unknown>"


def test_scan_finds_literal_reject_reason_and_records_the_line():
    found = {}
    scan_file("src/consensus/tx_verify.cpp", ALLMAN, found)
    assert list(found) == ["bad-txns-inputs-missingorspent"]
    (hit,) = found["bad-txns-inputs-missingorspent"]
    assert hit["function"] == "Consensus::CheckTxInputs"
    assert hit["lines"] == [5, 5]
    assert hit["idiom"] == "a"
    assert "src/consensus/tx_verify.cpp#L5-L5" in hit["permalink"]


def test_scan_handles_strprintf_idiom_by_stripping_the_format_tail():
    src = lines_of('''
bool Foo(Params p)
{
    return state.Invalid(TxValidationResult::TX_CONSENSUS, strprintf("bad-thing-%s", x));
}
''')
    found = {}
    scan_file("src/x.cpp", src, found)
    assert "bad-thing-" not in found and "bad-thing" in found
    assert found["bad-thing"][0]["idiom"] == "c"


def test_scan_ignores_block_comment_between_arguments():
    # Core writes `/*reject_reason=*/"bad-txnmrklroot"` -- the scanner must see through it.
    src = lines_of('''
static bool CheckMerkleRoot(const CBlock& block, BlockValidationState& state)
{
    return state.Invalid(
        /*result=*/BlockValidationResult::BLOCK_MUTATED,
        /*reject_reason=*/"bad-txnmrklroot",
        /*debug_message=*/"hashMerkleRoot mismatch");
}
''')
    found = {}
    scan_file("src/validation.cpp", src, found)
    assert "bad-txnmrklroot" in found


def test_clean_prefix_trims_trailing_punctuation():
    assert _clean_prefix("bad-thing-%s") == "bad-thing"
    assert _clean_prefix("prefix: %d") == "prefix"
