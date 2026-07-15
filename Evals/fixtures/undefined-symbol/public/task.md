# Task: make every runtime path valid

`process_order` passes the happy-path test but its validation and optional-cache paths contain invented or undefined APIs. Make all paths executable without globals. Invalid orders must raise `ValueError`; cache is optional and, when supplied, uses `get(key)` and `set(key,value)`. Preserve the function signature and do not swallow cache errors.
