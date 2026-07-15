import re
def extract_records(text):
    return [{"name": a, "value": b} for a, b in re.findall(r"(\w+):\s*(\w+)", text)]
