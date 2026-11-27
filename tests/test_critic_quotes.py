"""The critic's evidence check (on-04zje): quotes joined by an ellipsis, curly punctuation."""
from valxel_sdlc.evaluators.critic import quoted

DOC = """## Success metrics
- **M1:** At least 1 note persisted (a `tnote.note.persisted.v1` event) in at least 80% of sessions
  that open the page, over the first 2 weeks after release. This holds only if there are at least 5 sessions.
- **M2:** Of the notes created, 100% have a `tnote.note.persisted.v1` event with the same note id within 60 seconds of the created event.

## Agent notes
Assumed: U1 is the requester — not confirmed. See the [roadmap](roadmap/goals.yaml) for "GOAL-TNOTE-1".
"""


def test_exact_and_markdown_insensitive():
    assert quoted("at least 80% of sessions", DOC)
    assert quoted("M1: At least 1 note persisted", DOC)  # bold marks ignored
    assert not quoted("at least 90% of sessions", DOC)
    assert not quoted("ab", DOC)


def test_ellipsis_joins_excerpts_in_order():
    ev = ("M1: At least 1 note persisted (a `tnote.note.persisted.v1` event) in at least 80% of sessions ... over "
          "the first 2 weeks after release. This holds only if there are at least 5 sessions ... M2: ... 100% have a "
          "`tnote.note.persisted.v1` event with the same note id within 60 seconds of the created event.")
    assert quoted(ev, DOC)
    assert quoted("M1: At least 1 note…within 60 seconds", DOC)
    assert quoted("over the first 2 weeks [...] at least 5 sessions", DOC)


def test_ellipsis_still_refuses_invented_or_reordered_text():
    assert not quoted("M1: At least 1 note ... 95% have a matching event", DOC)  # second excerpt invented
    assert not quoted("within 60 seconds ... M1: At least 1 note", DOC)  # out of order
    assert not quoted("... ...", DOC)


def test_curly_quotes_dashes_and_links():
    assert quoted("U1 is the requester - not confirmed", DOC)
    assert quoted("Assumed: U1 is the requester — not confirmed", DOC)
    assert quoted("See the roadmap for “GOAL-TNOTE-1”", DOC)
    assert quoted("\"at least 80% of sessions\"", DOC)
