"""Recovery-Strategien."""
RECOVERY_STRATEGIES = ("recapture", "re-vision", "wait-retry", "scroll-retry", "relaunch", "abort")
def get_strategy(attempt: int) -> str:
    return RECOVERY_STRATEGIES[attempt] if attempt < len(RECOVERY_STRATEGIES) else "abort"
