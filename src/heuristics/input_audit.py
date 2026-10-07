"""Guard real LinTim experiments against the team's Edge.giv fallback.

LinTim Edge.giv columns 5/6 are travel-time bounds, not frequency bounds.
See core/io/ptn.py:process_link/process_load and core/model/ptn.py:Link.
Do not construct a new demand assignment implicitly when Load.giv is absent.
"""


def audit_lintim_frequency_inputs(ptn, allow_legacy=False):
    missing = sorted(set(ptn.edges) - set(ptn.loads))
    # The shared helper falls back to Edge values when either Load bound is 0.
    nonpositive = sorted(e for e, (_, lo, hi) in ptn.loads.items()
                         if e in ptn.edges and (lo <= 0 or hi <= 0))
    issues = []
    if missing:
        issues.append(f"Missing Load.giv rows for edges {missing}.")
    if nonpositive:
        issues.append(f"Load bounds require explicit zero-bound semantics on edges {nonpositive}.")
    if issues and not allow_legacy:
        raise ValueError(" ".join(issues) +
                         " The shared helper would substitute Edge.giv travel-time bounds as frequencies."
                         " Supply verified frequency inputs; --allow-legacy-frequency-bounds is for"
                         " diagnostic reproduction only, not validated LinTim results.")
    return {"frequency_inputs_verified_for_shared_helper": not issues,
            "legacy_diagnostic": bool(issues), "issues": issues}
