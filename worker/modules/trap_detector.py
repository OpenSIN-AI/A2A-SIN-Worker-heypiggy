"""Bot-Fallen erkennen."""
TRAP_INDICATORS = ("display:none", "visibility:hidden", "opacity:0", "aria-hidden")
HONEYPOT_NAMES = ("email", "name", "phone", "address", "url", "website")
def detect_trap(html: str) -> bool:
    return any(i in html.lower() for i in TRAP_INDICATORS)
def is_honeypot(name: str) -> bool:
    return any(h in name.lower() for h in HONEYPOT_NAMES)
