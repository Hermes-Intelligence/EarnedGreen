from pathlib import PurePosixPath

def approved_guidance(documents):
    if not isinstance(documents, dict):
        raise ValueError("documents")
    result, total = [], 0
    for path in sorted(documents):
        text = documents[path]
        if not isinstance(path, str) or not isinstance(text, str):
            continue
        if "\\" in path or path.startswith("/"):
            continue
        parts = PurePosixPath(path).parts
        if ".." in parts or len(parts) < 3 or parts[:2] != ("policies", "approved") or not path.endswith(".md"):
            continue
        if len(text) > 10000 or total + len(text) > 20000:
            continue
        result.append({"path": path, "content": text}); total += len(text)
    return result
