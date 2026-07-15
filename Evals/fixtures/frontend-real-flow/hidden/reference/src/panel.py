from html import escape

def render_panel(state):
    if not isinstance(state, dict): raise ValueError("state")
    kind = state.get("kind")
    if kind == "loading": return '<div role="status" aria-live="polite">Loading results...</div>'
    if kind == "empty": return '<div role="status" aria-live="polite">No results</div>'
    if kind == "error":
        message = state.get("message")
        if not isinstance(message, str): raise ValueError("message")
        return '<div role="alert">' + escape(message) + ' <button type="button" data-action="retry">Retry</button></div>'
    if kind == "data":
        items = state.get("items")
        if not isinstance(items, list): raise ValueError("items")
        names = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str): raise ValueError("item")
            names.append('<li>' + escape(item["name"]) + '</li>')
        return '<ul aria-label="Results">' + ''.join(names) + '</ul>'
    raise ValueError("kind")
