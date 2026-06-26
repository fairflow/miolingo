#!/usr/bin/env python3
"""
Proof-of-concept: parse espeak-ng phsource phoneme tables into a per-phoneme
record carrying (a) espeak mnemonic, (b) IPA, (c) espeak articulatory feature
mnemonics. This is the SOURCE-OF-TRUTH extractor for the tolerance table.

Run:  python3 extract_features.py <phsource_dir> <table_file e.g. ph_french>
"""
import re, sys, os

# espeak feature mnemonics we care about (from docs/phonemes.md)
MANNER = {'nas','stp','afr','frc','flp','trl','apr','clk','ejc','imp','vwl','lat','sib','liquid','rhotic'}
PLACE  = {'blb','lbd','bld','dnt','alv','pla','rfx','alp','pal','vel','lbv','uvl','phr','glt'}
VOICE  = {'vls','vcd'}
VHEIGHT= {'hgh','smh','umd','mid','lmd','sml','low'}
VBACK  = {'fnt','cnt','bck'}
VROUND = {'unr','rnd'}
ALLFEAT = MANNER|PLACE|VOICE|VHEIGHT|VBACK|VROUND

def parse_table(path):
    text = open(path, encoding='utf-8', errors='replace').read()
    # strip // comments
    out = {}
    blocks = re.split(r'\bphoneme\b', text)
    for b in blocks[1:]:
        # name is first whitespace-delimited token
        m = re.match(r'\s+(\S+)', b)
        if not m: continue
        name = m.group(1)
        body = b[:b.find('endphoneme')] if 'endphoneme' in b else b
        # remove comments
        body = re.sub(r'//.*', '', body)
        toks = set(re.findall(r'[A-Za-z_]+', body))
        feats = sorted(toks & ALLFEAT)
        ipa_m = re.search(r'\bipa\s+(\S+)', body)
        ipa = ipa_m.group(1) if ipa_m else None
        imp_m = re.search(r'import_phoneme\s+(\S+)', body)
        call_m = re.search(r'\bCALL\s+(\S+)', body)
        out[name] = dict(feats=feats, ipa=ipa,
                         imports=imp_m.group(1) if imp_m else None,
                         calls=call_m.group(1) if call_m else None)
    return out

if __name__ == '__main__':
    d, tbl = sys.argv[1], sys.argv[2]
    res = parse_table(os.path.join(d, tbl))
    for name, r in sorted(res.items()):
        if not (r['feats'] or r['ipa'] or r['imports'] or r['calls']): continue
        ipa = r['ipa'] or ('=%s'%name if not r['imports'] else '')
        print(f"{name:8s} ipa={str(r['ipa']):10s} feats={','.join(r['feats']):30s} "
              f"imp={r['imports'] or '':12s} call={r['calls'] or ''}")
