"""Registry consistency: every Fact type is wired everywhere, exactly once.

Adding a new card type must only require touching the canonical registries in
``mnemo.core.config`` (default targets) and ``mnemo.anki.adapter`` (builders);
these tests fail loudly if any layer falls out of sync.
"""

from mnemo.anki import adapter
from mnemo.core import config
from mnemo.core.card_schema import FACT_TYPES, Fact


# One minimal valid Fact per type (content shapes mirror tests/test_card_schema).
_MINIMAL_CONTENT = {
    "qa": {"front": "Q?", "back": "A"},
    "cloze": {"text": "A {{c1::cloze}}"},
    "list": {"title": "Steps", "items": ["one", "two"]},
    "typed": {"prompt": "Type it", "answer": "answer"},
    "image_occlusion": {
        "image": "diagram.png",
        "masks": [
            {"shape": "rect", "left": 0.1, "top": 0.1, "width": 0.2, "height": 0.2}
        ],
    },
}


def test_fact_types_match_default_models_targets_and_builders():
    assert set(FACT_TYPES) == set(config.DEFAULT_FACT_TARGETS)
    assert set(FACT_TYPES) == set(adapter._BUILDERS)


def test_adapter_targets_are_the_config_registry_not_a_copy():
    assert adapter._DEFAULT_MODELS is config.DEFAULT_FACT_TARGETS
    assert config.Config().target_note_types == config.DEFAULT_FACT_TARGETS


def test_placeholders_cover_every_fact_type():
    assert set(_MINIMAL_CONTENT) == set(FACT_TYPES)
    for fact_type, content in _MINIMAL_CONTENT.items():
        fact = Fact.from_dict(
            {"type": fact_type, "content": content, "deck": "Deck"}
        )
        image_name = "diagram.png" if fact_type == "image_occlusion" else None
        placeholders = adapter._placeholders(fact, image_name=image_name)
        assert placeholders, fact_type
        assert all(isinstance(value, str) for value in placeholders.values())
