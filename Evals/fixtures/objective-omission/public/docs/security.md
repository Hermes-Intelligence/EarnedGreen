# Security and metadata requirements

- **POL-010:** Copy `metadata` only when it is an object; otherwise reject the request. Default to an empty object.
- **POL-011:** Remove metadata keys equal to `secret`, `token`, `password`, or `api_key`, case-insensitively.
- **POL-012:** Secret-key filtering is recursive through nested objects and lists; do not modify non-secret values.

Security note: an empty object after recursive filtering is valid and must remain present in output.
