"""Inventory, registry (approval gate), alignment parsing, context, gate."""

import json

import pytest

from realised_phone import gate, inventory
from realised_phone.align import context_of, parse_mfa_json, words_of
from realised_phone.registry import ModelNotApproved, Registry, RegistryEntry

from conftest import FIXTURES


def test_en_es_inventory_rhotics():
    inv = inventory.load("en", "es")
    r = inv.target("r")
    assert r.canonical.phone == "r" and r.canonical.cls == "trill"
    assert {"ɾ", "ɹ", "ɻ", "ʁ"} <= set(r.phones)
    assert r.phone_class["ɹ"] == r.phone_class["ɻ"] == "english_r"
    assert r.detector == "rhotic"
    # coda neutralisation: tap or trill both correct in codas
    assert set(r.accepted_classes("coda")) == {"trill", "tap"}
    assert r.accepted_classes("intervocalic") == ["trill"]


def test_every_target_has_one_canonical_and_ipa_keys():
    inv = inventory.load("en", "es")
    for key, t in inv.targets.items():
        assert t.canonical.phone == key
        assert "g" not in key  # ASCII g normalised to IPA ɡ


def test_unknown_pair_raises():
    with pytest.raises(FileNotFoundError):
        inventory.load("xx", "es")


def test_shipped_registry_loads_and_gates():
    reg = Registry.load()
    ids = {e.id for e in reg.entries()}
    assert {"mfa-spanish_mfa", "fb-xlsr-53-espeak", "rhotic-detector", "whisper-gate"} <= ids
    for e in reg.entries():
        if e.status != "approved":
            with pytest.raises(ModelNotApproved):
                reg.require(e.id)
            if e.status == "candidate":
                assert reg.require(e.id, allow_candidates=True) is e


def test_registry_rules():
    reg = Registry([RegistryEntry("a", "detector", "1", "approved", approved_by="M", approved_on="2026-10-01"),
                    RegistryEntry("r", "detector", "1", "retired")])
    assert reg.require("a").id == "a"
    with pytest.raises(ModelNotApproved):
        reg.require("r", allow_candidates=True)     # retired is never usable
    with pytest.raises(ModelNotApproved):
        reg.require("missing", allow_candidates=True)


def test_registry_rejects_approval_without_approver(tmp_path):
    p = tmp_path / "reg.yaml"
    p.write_text("- {id: x, kind: detector, version: '1', status: approved}\n")
    with pytest.raises(ValueError):
        Registry.load(p)


def test_parse_real_mfa_output_and_contexts():
    al = parse_mfa_json(json.loads((FIXTURES / "mfa_es_correctamente.json").read_text()))
    assert [w.label for w in al.words][-1] == "correctamente"
    i = next(i for i, p in enumerate(al.phones) if p.label == "r")
    assert al.words[al.phones[i].word_index].label == "correctamente"
    assert context_of(al, i) == "intervocalic"
    # dental t keeps its diacritic (IPA, NFC)
    assert "t̪" in {p.label for p in al.phones}
    assert all(p.word_index is not None for p in al.phones)


def test_words_of_keeps_accents_and_drops_punctuation():
    assert words_of("¿Dónde está el perro?") == ["dónde", "está", "el", "perro"]


def test_gate_word_recall_accent_insensitive():
    g = gate.check("el perro está aquí", "el perro esta aqui")
    assert g.passed and g.word_recall == 1.0
    g = gate.check("el perro rojo", "hello there")
    assert not g.passed and "perro" in g.missing_words
    assert not gate.check("el perro", None).passed
