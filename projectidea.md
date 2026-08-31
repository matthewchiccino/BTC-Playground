# Project Idea: Consensus Lab 
**Subtitle:** Break Bitcoin's Consensus Rules on Purpose

## 💡 Elevator Pitch
An interactive web sandbox that demystifies Bitcoin Core. It allows users to craft deliberately invalid Bitcoin blocks and transactions, submit them to a local test network, and instantly see exactly *where* and *why* Bitcoin Core rejects them at the C++ source code level. 

## 🎯 The User Experience
The user is presented with a visual, editable structure of a Bitcoin block/transaction. They can click fields and mutate them (e.g., swapping two transaction IDs, bumping a coinbase output). 

Upon submission, the UI displays three panes:
1. **The Payload:** The raw hex code sent to the node.
2. **The Verdict:** Bitcoin Core's verbatim rejection string (e.g., `bad-txns-in-belowout`).
3. **The Source:** The actual snippet of C++ code that caught the error (e.g., from `src/validation.cpp`), deep-linked to the exact line in the Bitcoin Core GitHub repository.
*Optional bonus:* A live terminal pane streaming `debug.log` to show the node's real-time reaction.

## 🛠️ Technical Architecture
* **Frontend:** React. Handles the visual block builder and displays the three-pane output.
* **Backend:** FastAPI wrapper. Handles requests from the frontend and communicates with the Bitcoin node. Use Core's Python testing tools (`messages.py` and `blocktools.py`) to handle the complex serialization of blocks rather than building it from scratch.
* **The Node:** A single Bitcoin Core node running in `regtest` mode. 

**Architectural Insight (Stateless Validation):**
The app can serve multiple concurrent users using just *one* shared `regtest` node. Because the goal is simply to get Core's validation verdict, you don't need to actually broadcast the attacks or mutate the chain. By using read-only RPC calls (`testmempoolaccept` for transactions, and `getblocktemplate` with `{"mode": "proposal"}` for blocks), the node returns the exact rejection string with zero state mutation.

## 🗺️ Project Scope & Roadmap

### Phase 1: The Weekend MVP
A single-page deployment featuring three basic attacks:
* **Double Spend:** Trying to spend the same UTXO twice.
* **Coinbase Over-subsidy:** Minting just 1 satoshi more than allowed.
* **Bad Merkle Root:** Mutating a transaction without updating the root.

### Phase 2: The Semester Project (Advanced)
Write an independent validator from scratch in Rust or Go, implementing one consensus rule at a time. Build a differential testing harness that feeds identical blocks to both *your* validator and Bitcoin Core, then diffs the verdicts. Disagreements highlight edge cases and solidify actual consensus understanding.

## 💼 Professional Framing (For Resume/Interviews)
This project sits perfectly at the intersection of Software Engineering (systems depth) and Product Management (user narrative). 

* **For SWEs:** Demonstrates backend architecture, stateless API design, differential testing, and the ability to navigate and comprehend a massive, legacy C++ codebase.
* **For PMs:** Demonstrates the ability to take an incredibly opaque, highly technical system and make it legible, interactive, and educational for end users.