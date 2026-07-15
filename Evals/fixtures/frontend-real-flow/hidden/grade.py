import importlib.util, json, sys
from html.parser import HTMLParser
from pathlib import Path

p = Path(sys.argv[1]) / "src/panel.py"
spec = importlib.util.spec_from_file_location("panel", p)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
checks = []
def check(i, v): checks.append((i, bool(v)))
def rejects(v):
    try: m.render_panel(v); return False
    except ValueError: return True
    except Exception: return False


class Collected(HTMLParser):
    def __init__(self):
        # convert_charrefs=True unescapes both named (&lt;) and numeric (&#60;)
        # entity forms in text data, so the checks below are agnostic to which
        # escaping the implementation chose; attribute values are likewise
        # unescaped and quote-style (single/double) is normalized away.
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.data_parts = []
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
    def handle_data(self, data):
        self.data_parts.append(data)


def parse(html_string):
    collector = Collected()
    collector.feed(html_string)
    collector.close()
    return collector


def has_attr(collector, attr, value):
    return any(attributes.get(attr) == value for _, attributes in collector.tags)


def has_tag_attr(collector, tag, attr, value):
    return any(name == tag and attributes.get(attr) == value for name, attributes in collector.tags)


def tag_names(collector):
    return [name for name, _ in collector.tags]


def text_of(collector):
    return "".join(collector.data_parts)


try:
    loading = m.render_panel({"kind":"loading"}); empty = m.render_panel({"kind":"empty"})
    error = m.render_panel({"kind":"error","message":"Failed <script>alert(1)</script>"})
    data = m.render_panel({"kind":"data","items":[{"name":"<Admin>"},{"name":"Zoë"}]})

    status_ok = all(
        has_attr(parse(x), "role", "status") and has_attr(parse(x), "aria-live", "polite")
        for x in [loading, empty]
    )
    check("status-states", status_ok)

    error_dom = parse(error)
    # No real <script> element must be produced; the payload must survive only as
    # inert, escaped text (so "<script>" shows up in text data, not as a tag).
    error_ok = (
        has_attr(error_dom, "role", "alert")
        and "script" not in tag_names(error_dom)
        and "<script>alert(1)</script>" in text_of(error_dom)
        and has_tag_attr(error_dom, "button", "type", "button")
        and has_tag_attr(error_dom, "button", "data-action", "retry")
    )
    check("error-accessible-safe", error_ok)

    data_dom = parse(data)
    data_ok = (
        "ul" in tag_names(data_dom)
        and has_tag_attr(data_dom, "ul", "aria-label", "Results")
        and "li" in tag_names(data_dom)
        and "admin" not in tag_names(data_dom)  # <Admin> must not become a real element
        and "<Admin>" in text_of(data_dom)
        and "Zoë" in text_of(data_dom)
    )
    check("data-semantic-safe", data_ok)

    check("invalid", rejects({"kind":"mystery"}) and rejects({"kind":"data","items":[{}]}) and rejects(None))
except Exception: check("execution", False)
n = sum(v for _, v in checks)
print(json.dumps({"passed": n == len(checks), "score": 100*n/len(checks), "checks": [{"id": i, "passed": v} for i,v in checks]}))
sys.exit(0 if n == len(checks) else 1)
