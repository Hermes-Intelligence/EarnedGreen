# Outcome adapter contract

Routing tests prove only that the right context/model profile was selected. They do not prove that an agent produced better code.

An outcome adapter must:

- create a clean disposable copy of a public fixture;
- expose the same task, budget and starting state to every arm;
- keep `Evals/hidden` outside the agent-visible workspace;
- record provider, actual resolved model, effort, tokens, elapsed time, tool calls and human interventions;
- invoke the hidden grader only after the agent process exits;
- preserve stdout, stderr, changed-file manifest and grader evidence;
- reject runs where the agent could read hidden tests or another arm's output.

Provider-specific launch commands and credentials are local configuration, not committed policy. No adapter may silently change a user's default model.
