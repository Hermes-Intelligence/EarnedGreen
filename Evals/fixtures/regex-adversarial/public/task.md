# Task: robust record extraction

Fix `extract_records(text)` in `src/extractor.py`. Records are lines in `name: value` form. Ignore blank/comment lines, trim outer whitespace, accept Unicode names, preserve values including colons, support CRLF/LF, skip malformed lines and stay linear on 200,000 malformed characters. Do not encode observed names in a list or use a backtracking-prone pattern.
