# Task: evolve a public function safely

Add keyword-only `discount=0` to `calculate_total(items, tax_rate=0)` and apply discount before tax. Validate discount from 0 through 1. Preserve all old positional callers and return type. Do not rename or remove the public function.
