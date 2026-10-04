# 0001: Validate with read-only RPCs; never mutate the node

**Status:** Accepted

**Context.** The app lets anonymous visitors send crafted, deliberately invalid
data toward one shared Bitcoin node. We only need Core's *verdict*.

**Decision.** Transactions go through `testmempoolaccept`; blocks through
`getblocktemplate` with `{"mode": "proposal"}`. Both return the exact rejection
string and change nothing. `/submit` never calls `sendrawtransaction`,
`submitblock`, or any mining RPC.

**Consequences.**
- One node safely serves everyone concurrently; no per-user state, no cleanup.
- A unit test asserts that for every scenario `/submit` only invokes those two methods.
- We can't demonstrate effects that need a real state change (reorgs, mempool replacement). Accepted limitation.
- Some rejections are only visible in proposal mode / mempool acceptance, not by actually connecting a block; scenarios are chosen with that in mind.
