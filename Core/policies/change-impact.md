# Change Impact Assurance

Apply when a function signature, public symbol, data schema, API, event, configuration key, database contract or serialization format changes.

Record:

- definitions and declarations,
- direct and indirect call sites,
- implementers and consumers,
- imports/exports and generated artifacts,
- tests and contract fixtures,
- compatibility, migration and rollback obligations,
- documentation and observability affected.

Verification must include the narrow check and the widest affordable integration check. If a touched public symbol has call sites in files never inspected, completion is blocked until they are reviewed or explicitly excluded with evidence.
