# The host pages' questions (class G of locus docs/neolingo-test-design.md)

The review page (`/review`) and the flick deck (port 8812) are the host's own pages. The app's page has its own
questions, U1 to U11 in locus `docs/neolingo-page-questions.md`; this list follows that one's form.

**The script WRITES (a guest's take, judgements, a flick verdict). Run it ONLY on a scratch host, NEVER on the real
host (8810) or the real flick deck.** Use a scratch host on a COPY of `var/` (step 1 of the README's update), for
example `NEOLINGO_VAR=<copy> NEOLINGO_SLOTS=2 ./run.sh --port 8811`. Run the flick server from a copy of this folder,
because it keeps its decks and verdicts in `var/flick/` beside itself.

When the review page, `host.js` or the flick page changes, a browser agent plays the script at 375 px. It answers
each question YES or NO, with a screenshot or the element's text as evidence. A NO is checked once more from a fresh
start before it is reported. The YES/NO table goes to the overseer with the host commit.

## The script

1. Scratch host, slot 2: Continue as a guest; load the test list; record a take; Check.
2. Scratch host: open `/review` with "not yet judged" off. Find the newest card from the copied archive whose phrase
   has more than one word. In `<copy>/archive/overseer_takes.txt`, list one take of the copy (first field: its token)
   and reload `/review`.
3. Flick, on the copy: open a deck, judge one card with a note typed or dictated, then reopen the deck.

## The questions

| | question | the fault that occurred |
|---|---|---|
| HP1 | On `/review`, a card's Heard row shows the sounds grouped word by word, as the engine grouped them. Where only the recogniser's raw run exists, it is labelled "(ungrouped)". | 13 October, the owner's note on "Ich weiß nicht": "heard sounds still without spaces". The review page showed the recogniser's raw run (fixed 2ea7ba8). |
| HP2 | The listed take carries "Mac voice (test)". "hide test voices" removes it from the list and from the count, and no other card is removed. | 13 October: the overseer's Mac-voice takes were listed among the owner's takes. Three of them carry judgements in the archive (fixed 66ff9a5; the CHOOSE / JUDGE split leaves them out). |
| HP3 | The guest's take of step 1 has no card on `/review`, and the app draws no "Was this result fair?" controls under the guest's result. | 13 October (found by reading): a guest's takes were kept, archived and open to judging (fixed 4dcdaf3). |
| HP4 | On the flick deck at 375 px, the card's sound plays. After the reopen, the judged card shows its verdict and its note again. | No fault recorded: a designed question for the deck, the owner's cheap channel (design 4G, 6). Drop it if a question must name a fault. |

Left out on purpose: what `tests/check_host.py` already checks over HTTP (the archive's filters, paging, refused
judgements, the review page's title and its two labels as text, `host.js` under node), and matters of wording or
taste, which a question cannot judge.
