"""Neolingo's environment: the outside world as a few functions.

target_ipa, audible, hear, sounds, gloss, cost_table, variants.
Wraps Miolingo's own code (see _miolingo.py); no Streamlit."""
from .variants import variants, variant
from .ipa import target_ipa, norm_word, phones_of, join_length
from .audio_level import audible
from .hearing import hear, preload, ModelMissing
from .soundcheck import sounds
from .gloss import gloss
from .tables import cost_table, write_cost_table, reference_score

__all__ = ["variants", "variant", "target_ipa", "norm_word", "phones_of", "join_length", "audible",
           "hear", "preload", "ModelMissing", "sounds", "gloss", "cost_table",
           "write_cost_table", "reference_score"]
