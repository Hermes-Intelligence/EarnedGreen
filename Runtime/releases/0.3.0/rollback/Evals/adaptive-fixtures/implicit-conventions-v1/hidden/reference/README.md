# Reference gamma feed

Implements the gamma source exactly on the house conventions: loud failure on
error-shaped/empty payloads, scrub-before-resolve, append-only change log with
restate rows, published-date point-in-time keying, and rows via rows.make_row.
