import json

from mnemo.pipeline.flashcards.io import regenerate_sidecar_fingerprints, sha256_file


def test_regenerate_sidecar_fingerprints_updates_existing_sidecars_atomically(tmp_path):
    csv_path = tmp_path / "cards.csv"
    csv_path.write_text("CardID,Front\n1,Q\n", encoding="utf-8")
    manifest = csv_path.with_suffix(".manifest.json")
    coverage = csv_path.with_suffix(".coverage.json")
    manifest.write_text(json.dumps({"knowledge_units": []}), encoding="utf-8")
    coverage.write_text(json.dumps({"objectives": []}), encoding="utf-8")

    updated = regenerate_sidecar_fingerprints(csv_path)

    assert set(updated) == {manifest, coverage}
    expected = sha256_file(csv_path)
    assert json.loads(manifest.read_text())["fingerprints"]["csv_sha256"] == expected
    assert json.loads(coverage.read_text())["fingerprints"]["csv_sha256"] == expected
