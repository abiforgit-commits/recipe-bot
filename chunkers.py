"""Two chunking strategies for the recipe cards.

A chunk is the unit of retrieval: it is what gets embedded, stored, and
returned by a search. Task Set B's whole experiment is asking: does the way
we cut the cards change whether the right chunk comes back in the top 5?
"""

NAIVE_CHUNK_SIZE = 400  # characters
NAIVE_OVERLAP = 50      # characters repeated between neighbouring chunks


def chunk_naive(card):
    """The 'current' strategy: fixed-size character windows, blind to structure.

    Cuts every 400 characters regardless of what the cut lands on, so it can
    slice an ingredient row away from its table header or its recipe title.
    The overlap softens boundary cuts but does not fix them.
    """
    text = card["body"]
    chunks = []
    start = 0
    while start < len(text):
        piece = text[start:start + NAIVE_CHUNK_SIZE].strip()
        if piece:
            chunks.append(piece)
        start += NAIVE_CHUNK_SIZE - NAIVE_OVERLAP
    return chunks


def chunk_structure_aware(card):
    """One chunk per markdown section (## Ingredients, ## Method, ...).

    Two rules the naive chunker breaks and this one never does:
      1. A table is never split - the whole ingredient table travels as one
         chunk, so '20g rock salt' always sits next to its header row.
      2. Every chunk starts with the recipe title, so no chunk is ever
         orphaned from the recipe it belongs to.
    """
    title = card["meta"]["title"]
    sections = []
    current = []
    for line in card["body"].splitlines():
        if line.startswith("## ") and current:
            sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current).strip())

    chunks = []
    for section in sections:
        if not section:
            continue
        if section.startswith("# "):  # the intro section already has the title
            chunks.append(section)
        else:
            chunks.append(f"# {title}\n\n{section}")
    return chunks


STRATEGIES = {
    "naive": chunk_naive,
    "structure": chunk_structure_aware,
}
