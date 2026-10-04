# 0003: `/submit` accepts a token, never client bytes

**Status:** Accepted

**Context.** An earlier design took `payload_hex` from the client and fed it to the
node. Harmless to state (see 0001) but still an open door to lob arbitrary
malformed bytes at the shared node.

**Decision.** `/build` constructs the payload server-side and returns an opaque
`build_id`. `/submit` takes only that token and looks up what this process built
(`buildcache.py`, 120s TTL, bounded size). The request schema forbids extra fields.

**Consequences.**
- The node only ever sees payloads this server produced.
- The cache is deliberately memory-only and expiring: a cache, not a store (no persistence, per the project constraints).
- A user who waits too long gets 410 and clicks Build again.
- Token format is coupled to the API schema; a unit test keeps them in sync.
