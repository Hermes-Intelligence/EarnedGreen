def render_panel(state):
    return "<ul>" + "".join("<li>" + item["name"] + "</li>" for item in state.get("items", [])) + "</ul>"
