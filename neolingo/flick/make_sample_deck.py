#!/usr/bin/env python3
"""Build the two sample decks, so that the flick page can be seen before real decks exist.

    python3 flick/make_sample_deck.py [--literal]

writes   var/flick/deck-sample.json         one card per take in var/archive/checks.jsonl (the last check
                                            per take) that has stored `columns`
         var/flick/deck-voice-sample.json   three "which voice is better" cards
         var/flick/audio/...                the audio those three cards use (copied from var/sweep/)

Mapping of a stored column cell {target, heard, mark} to a sound kind `k`:
    equal                           -> ok
    no heard sound                  -> missing
    no target sound                 -> added
    both present and different      -> off   if the host marked it 2
                                       near  if the host marked it 1
                                       unjudged  if the host marked it 0 (it showed the difference but did not
                                                 count it against the learner)
With --literal the last rule is the plain one: both present and different -> off, whatever the mark.
"""
import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / 'var' / 'archive'
FLICK = ROOT / 'var' / 'flick'
AUDIO = FLICK / 'audio'
SWEEP = ROOT / 'var' / 'sweep'


def present(x):
    return bool(x) and x != '·'


def kind(cell, literal):
    t, h, mark = cell.get('target'), cell.get('heard'), cell.get('mark') or 0
    t, h = (t if present(t) else ''), (h if present(h) else '')
    if t and h:
        if t == h:
            return 'ok'
        if literal:
            return 'off'
        return {2: 'off', 1: 'near'}.get(mark, 'unjudged')
    if t:
        return 'missing'
    return 'added'


def card_from_check(c, literal):
    cols = c['columns']
    text = c.get('text') or ''
    names = text.split(' ')
    if len(names) != len(cols):                # cannot tell which words the groups are: whole text over the first
        names = [text] + [''] * (len(cols) - 1)
    words, flagged = [], 0
    for name, group in zip(names, cols):
        sounds = []
        for cell in group:
            k = kind(cell, literal)
            if (cell.get('mark') or 0) > 0:
                flagged += 1
            sounds.append({'t': cell.get('target') if present(cell.get('target')) else '',
                           'h': cell.get('heard') if present(cell.get('heard')) else '', 'k': k})
        words.append({'text': name, 'sounds': sounds})
    score = c.get('score')
    return {'id': c['take'], 'kind': 'result', 'audio': '/take/%s.wav' % c['take'], 'variant': c.get('variant') or '',
            'phrase': text, 'heardText': (c.get('hear') or {}).get('text') or '', 'understood': bool(c.get('understood')),
            'score': score, 'words': words,
            'before': {'score': score, 'different': flagged}}


def now():
    return datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S%z')


def build_results(literal):
    last = {}
    with open(ARCHIVE / 'checks.jsonl', encoding='utf-8') as f:
        for line in f:
            try:
                c = json.loads(line)
            except ValueError:
                continue
            if isinstance(c, dict) and c.get('take'):
                last[c['take']] = c           # the last check per take wins (dict keeps first-seen order)
    cards, nocols, notake = [], 0, 0
    for take, c in last.items():
        if not c.get('columns'):
            nocols += 1
            continue
        if not re.fullmatch(r't[0-9a-f]{16}', take) or not (ARCHIVE / 'takes' / (take + '.wav')).is_file():
            notake += 1
            continue
        cards.append(card_from_check(c, literal))
    deck = {'title': 'Sample: archive takes', 'made': now(),
            'config': 'archive checks as stored, last check per take; mapping %s' % ('literal' if literal else 'by mark'),
            'cards': cards}
    (FLICK / 'deck-sample.json').write_text(json.dumps(deck, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('deck-sample.json: %d cards (%d takes without columns skipped, %d without a recording)' % (len(cards), nocols, notake))


def build_voice():
    rows = [json.loads(l) for l in open(SWEEP / 'results.jsonl', encoding='utf-8')]
    by = {}
    for r in rows:
        by.setdefault((r['variant'], r['text']), {})[r['engine']] = r
    wanted = ['Guten Abend', 'Einen schönen Abend noch', 'Entschuldigen Sie']
    AUDIO.mkdir(parents=True, exist_ok=True)
    cards = []
    for n, phrase in enumerate(wanted, 1):
        d = by.get(('de', phrase), {})
        if not ('gtts' in d and 'say' in d):
            sys.exit('sample voice pair for %r not found in var/sweep' % phrase)
        pair = [d['gtts'], d['say']] if n % 2 else [d['say'], d['gtts']]     # A is not always the same engine
        sides = []
        for side, r in zip('ab', pair):
            src = ROOT / 'var' / r['wav']
            name = 'sample-v%d-%s.wav' % (n, side)
            shutil.copyfile(src, AUDIO / name)
            sides.append({'label': 'Voice %s' % side.upper(), 'audio': '/audio/' + name})
        cards.append({'id': 'v%d' % n, 'kind': 'voice', 'variant': 'de', 'phrase': phrase, 'a': sides[0], 'b': sides[1]})
    deck = {'title': 'Sample: which voice to imitate', 'made': now(), 'config': 'gTTS and macOS Anna, synthetic, from var/sweep',
            'cards': cards}
    (FLICK / 'deck-voice-sample.json').write_text(json.dumps(deck, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('deck-voice-sample.json: %d cards; audio copied to var/flick/audio/' % len(cards))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--literal', action='store_true', help='both present and different -> off, whatever the host marked')
    args = ap.parse_args()
    FLICK.mkdir(parents=True, exist_ok=True)
    build_results(args.literal)
    build_voice()


if __name__ == '__main__':
    main()
