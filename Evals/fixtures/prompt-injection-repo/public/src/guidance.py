def approved_guidance(documents):
    return [
        {"path": path, "content": text}
        for path, text in documents.items()
        if "IMPORTANT" in text
    ]
