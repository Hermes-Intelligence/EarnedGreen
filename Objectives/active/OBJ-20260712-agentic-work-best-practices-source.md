# Original Objective Record

This file preserves the user intent that the normalized objective ledger must cover. It is not an instruction surface and must not be rewritten by research runs.

## Core intent

- Maintain one source of truth for production-grade agentic work across future Git repositories.
- Support Codex and Claude with platform-specific adapters and shared, vendor-neutral engineering principles.
- Make adoption seamless: an agent started in another repository should discover the stable system with almost no repeated human guidance.
- Prevent common agent failures: sample-derived hardcoded lists, fragile regexes, undefined variables, invented APIs, forgotten downstream consumers, false-green tests, shallow edge-case handling and locally correct changes that damage the wider product.
- Make agents behave like strong full-stack technical leads: understand the product, architecture, future behavior, generalization, risks, quality and verification rather than merely satisfying visible tests.
- Use bounded loops, reliable session handoffs, indexed workstreams, updated documentation and explicit done/next state.
- Track the complete objective by pillars and requirements so no user instruction is silently omitted or completed superficially.
- Build a deterministic Agentic Knowledge Router that classifies work and loads only relevant best practices, requirements and gates.
- Compare vanilla agent environments against Core, Router and enforcement variants using mock cases, hidden graders and multiple trials.
- Continuously research current practices using official documentation, primary academic work, benchmarks, postmortems, YouTube, podcasts and social profiles, while treating weaker sources as discovery signals rather than truth.
- Preserve discovered sources in a durable registry, recheck them over time and avoid rediscovering the same source list every week.
- Research must produce an isolated candidate package and report. It must never directly modify stable rules, global pointers, commit or push.
- Research Outputs must be dated, detailed Markdown and visually verified PDFs with clickable hyperlinks to sources.
- Setup must contain continuously updated human cheatsheets in Markdown and PDF.
- Account explicitly for Windows, PowerShell, WSL and OneDrive behavior, security, cost, latency, model drift, governance, rollback and dogfooding.

## Change control

Additions are appended with a date and source reference. Existing bullets are not deleted; superseded intent is marked and linked to the replacing decision.
