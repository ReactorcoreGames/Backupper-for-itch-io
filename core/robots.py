"""robots.txt matching with wildcard support.

urllib.robotparser treats patterns as literal prefixes, so a rule like
"Disallow: /*/download/", which itch.io really uses, would never match.
"""

import re
from urllib.parse import urlsplit


def _compile(pattern):
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]
    body = ".*".join(re.escape(piece) for piece in pattern.split("*"))
    return re.compile(body + ("$" if anchored else ""))


class RobotRules:
    def __init__(self, text=""):
        self.crawl_delay = 0.0
        self._rules = []
        self._parse(text)

    def _parse(self, text):
        applies = False
        in_agent_lines = False
        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            field, value = (part.strip() for part in line.split(":", 1))
            field = field.lower()

            if field == "user-agent":
                if not in_agent_lines:
                    applies = False
                in_agent_lines = True
                if value == "*":
                    applies = True
                continue

            in_agent_lines = False
            if not applies:
                continue
            if field in ("allow", "disallow") and value:
                self._rules.append((len(value), field == "allow", _compile(value)))
            elif field == "crawl-delay":
                try:
                    self.crawl_delay = max(self.crawl_delay, float(value))
                except ValueError:
                    pass

    def allows(self, url):
        parts = urlsplit(url)
        target = parts.path or "/"
        if parts.query:
            target += f"?{parts.query}"
        # The longest matching rule wins, and Allow wins a tie.
        best_length, allowed = -1, True
        for length, is_allow, pattern in self._rules:
            if pattern.match(target) and (length > best_length or (length == best_length and is_allow)):
                best_length, allowed = length, is_allow
        return allowed
