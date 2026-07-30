# Reliability Contract

Map success and failure behavior separately. Test fresh, boundary, expired, duplicate, interrupted and recovery states. Retry or fallback only for explicitly transient failures, and propagate unexpected failures.

For caches and shared state, include identity boundaries, copy isolation, time-boundary equality, stale ceilings, tenant separation and falsy-but-valid data. For resumable work, verify idempotency keys, atomic checkpoints, corrupt state, input mismatch and cleanup.

Public green is not completion evidence when it exercises only the happy path. Add focused boundary and failure-injection checks derived from the public contract.
