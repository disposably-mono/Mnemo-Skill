"""Tests for the Filipino/English page-language classifier (mnemo/ingest/language.py)."""

from mnemo.ingest.language import classify_language


def test_classifies_filipino_prose():
    text = (
        "Ang wikang panturo ang ginagamit sa pagtuturo sa mga eskuwelahan "
        "at ang wika sa pagsulat ng mga aklat at kagamitan sa silid-aralan."
    )
    assert classify_language(text) == "fil"


def test_classifies_english_prose():
    text = (
        "The medium of instruction is the language used for teaching in "
        "schools and the language for writing books and materials for the classroom."
    )
    assert classify_language(text) == "eng"


def test_returns_unknown_for_text_with_no_markers():
    assert classify_language("ATP synthase mitochondria 42") == "unknown"


def test_returns_unknown_for_empty_text():
    assert classify_language("") == "unknown"


def test_returns_unknown_on_a_tie():
    # Contrived to hit an exact tie between marker counts.
    assert classify_language("ang the") == "unknown"


def test_is_case_insensitive():
    text = "ANG WIKANG PANTURO AY GINAGAMIT SA MGA ESKUWELAHAN"
    assert classify_language(text) == "fil"


def test_short_page_with_embedded_quote_in_the_other_language_can_still_favor_host_language():
    # A predominantly-Filipino page that quotes a short English phrase should
    # still classify as Filipino as long as Filipino markers dominate overall.
    text = (
        "Ang mga salik na ito ay batay sa isang ulat noong 1934 na "
        "nagsasabing \"the vernaculars are outgrowths of the Malay\" ayon "
        "sa lupon, ngunit ang pangkalahatang konklusyon ng ulat na ito ay "
        "pabor sa Tagalog bilang batayan ng wikang pambansa."
    )
    assert classify_language(text) == "fil"


def test_quoted_span_is_excluded_from_the_word_count():
    # A long quoted English passage must not outweigh a short Filipino host
    # sentence just because the quote itself has more marker words.
    text = (
        'Sinabi niya: "On theoretic and scientific grounds, no one hesitates '
        'to give preference to Tagalog as the best developed and fittest '
        "dialect to be selected as a common national language for the whole "
        'Philippine Archipelago and its relation to the national capital." '
        "Ito ang sinabi niya noong 1924."
    )
    assert classify_language(text) == "fil"
