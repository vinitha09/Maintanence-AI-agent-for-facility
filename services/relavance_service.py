
def filter_relevant_chunks(
    matches: list[dict],
    max_distance: float = 0.7,
) -> list[dict]:
    """
    Keep chunks whose cosine distance is below the
    configured threshold.

    The threshold is an initial setting and must be
    evaluated against real test questions.
    """
    return [
        match
        for match in matches
        if match.get("distance") is not None
        and match["distance"] <= max_distance
    ]
