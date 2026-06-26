#!/usr/bin/env python3
"""
Re-evaluate the cached results.json with a FAIR normalization, then compute:
  - normalized PER on correct items (per model)
  - error-detection: per-item PER on 'error' items should exceed a threshold,
    while 'correct' items stay below it  ->  ROC-ish separation
  - wav2vec2 abstention analysis: relate min/mean CTC confidence to PER, and
    show what an abstain rule would do (abstain when min_conf < tau).

Normalization rationale (KEY FINDING): facebook/wav2vec2-lv-60-espeak-cv-ft emits
a 392-token MULTILINGUAL phoneme vocab that includes tone digits (a5, i2), retroflex
dots (s., ts.), and length marks (eː). espeak (v1.48) IPA does not use these. To
compare phone *identity* fairly we fold both sides to a base-phone set:
  - drop tone digits 0-9, dots, length 'ː', stress, nasal-tie kept->folded
  - fold r-family {ɹ ɾ ʁ r ʀ} -> 'r'  (espeak uses ɹ/ɾ; model often ʁ/r)
  - fold central/near vowels lightly (ɐ->a, ɨ->i, ʊ->u, ə kept)
This makes PER a measure of "did it get the right broad phone", which is what
matters for learner feedback (and is generous to BOTH models equally).
"""
import json, os, re, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "results", "results.json")))

R_FAMILY = set("ɹɾʁrʀ")
FOLD = {"ɐ": "a", "ɑ": "a", "ɒ": "a", "ä": "a",
        "ɨ": "i", "ɪ": "i", "ᵻ": "i",
        "ʊ": "u", "ɯ": "u",
        "ʒ": "ʒ", "x": "x"}

def base(tok):
    # strip combining marks
    tok = "".join(c for c in unicodedata.normalize("NFD", tok)
                  if not unicodedata.combining(c))
    tok = re.sub(r"[0-9]", "", tok)          # tone digits
    tok = tok.replace(".", "").replace("ː", "").replace("ˑ", "")
    tok = tok.replace("ˈ", "").replace("ˌ", "")
    if not tok:
        return ""
    # fold r-family on first char
    out = []
    for ch in tok:
        if ch in R_FAMILY:
            out.append("r")
        else:
            out.append(FOLD.get(ch, ch))
    s = "".join(out)
    # collapse a multi-char diphthong token to its first vowel for identity compare
    return s

def toks(phone_str):
    # phone_str like "/k a ʃ o v ʊ/"
    s = phone_str.strip().strip("/").strip()
    return [t for t in (base(x) for x in s.split()) if t]

def lev(a, b):
    n, m = len(a), len(b)
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev = dp[0]; dp[0] = i
        for j in range(1, m + 1):
            cur = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1,
                        prev + (0 if a[i-1] == b[j-1] else 1))
            prev = cur
    return dp[m]

def per(ref, hyp):
    if not ref:
        return 0.0 if not hyp else 1.0
    return lev(ref, hyp) / len(ref)

print("FAIR (normalized) re-evaluation\n" + "="*70)
summary = {}
for mk, mv in R.items():
    if "rows" not in mv:
        print(f"{mk}: FAILED"); continue
    correct, errors = [], []
    print(f"\n##### {mk}: {mv['name']}  (load {mv.get('load_t',0):.1f}s)")
    print(f"{'id':22s}{'kind':8s}{'PERvsIntended':>14s}{'PERvsSpoken':>13s}  conf")
    rows_out = []
    for r in mv["rows"]:
        ref = toks(r["ref"]); spk = toks(r["spoken_ipa"]); hyp = toks(r["hyp"])
        pi = per(ref, hyp); ps = per(spk, hyp)
        conf = ""
        if "min_conf" in r:
            conf = f"mean={r['mean_conf']} min={r['min_conf']}"
        print(f"{r['id']:22s}{r['kind']:8s}{pi:14.2f}{ps:13.2f}  {conf}")
        rec = dict(id=r["id"], kind=r["kind"], per_intended=round(pi,3),
                   per_spoken=round(ps,3))
        if "min_conf" in r:
            rec["min_conf"]=r["min_conf"]; rec["mean_conf"]=r["mean_conf"]
        rows_out.append(rec)
        if r["kind"] == "correct":
            correct.append(pi)
        else:
            errors.append(pi)
    ac = sum(correct)/len(correct)
    ae = sum(errors)/len(errors)
    print(f"  --> avg PER correct items   = {ac:.3f}")
    print(f"  --> avg PER on error items  = {ae:.3f} (vs intended; higher=error visible)")
    summary[mk] = dict(avg_per_correct=round(ac,3),
                       avg_per_error_items_vs_intended=round(ae,3),
                       rows=rows_out)

# ---- Error detection separation: pick threshold on PERvsIntended ----
print("\n" + "="*70)
print("ERROR-DETECTION separation (flag 'wrong' when PERvsIntended > tau)")
for mk, mv in R.items():
    if "rows" not in mv: continue
    cor = [per(toks(r['ref']), toks(r['hyp'])) for r in mv['rows'] if r['kind']=='correct']
    err = [per(toks(r['ref']), toks(r['hyp'])) for r in mv['rows'] if r['kind']=='error']
    print(f"\n{mk}: correct PERs sorted: {sorted(round(x,2) for x in cor)}")
    print(f"{mk}: error   PERs sorted: {sorted(round(x,2) for x in err)}")
    # best threshold by accuracy
    best=None
    for tau in [x/100 for x in range(0,201,5)]:
        tp=sum(1 for e in err if e>tau); fp=sum(1 for c in cor if c>tau)
        tn=len(cor)-fp; fn=len(err)-tp
        acc=(tp+tn)/(len(cor)+len(err))
        if best is None or acc>best[0]:
            best=(acc,tau,tp,fp,tn,fn)
    acc,tau,tp,fp,tn,fn=best
    print(f"{mk}: best tau={tau:.2f} acc={acc:.2f}  TP(err caught)={tp}/{len(err)} "
          f"FP(false alarm)={fp}/{len(cor)}")

# ---- wav2vec2 abstention ----
print("\n" + "="*70)
print("ABSTENTION (wav2vec2): would low confidence have caught the bad cases?")
mv = R.get("wav2vec2")
if mv and "rows" in mv:
    rows=[(r['id'],r['kind'],r['min_conf'],r['mean_conf'],
           per(toks(r['ref']),toks(r['hyp']))) for r in mv['rows'] if 'min_conf' in r]
    rows.sort(key=lambda x:x[2])
    print(f"{'id':22s}{'kind':8s}{'min_conf':>9s}{'mean_conf':>10s}{'PER':>7s}")
    for i,k,mn,me,p in rows:
        print(f"{i:22s}{k:8s}{mn:9.3f}{me:10.3f}{p:7.2f}")
    # correlation min_conf vs PER
    import statistics
    mc=[x[2] for x in rows]; pe=[x[4] for x in rows]
    n=len(mc); mmc=sum(mc)/n; mpe=sum(pe)/n
    cov=sum((a-mmc)*(b-mpe) for a,b in zip(mc,pe))/n
    sc=statistics.pstdev(mc); sp=statistics.pstdev(pe)
    corr=cov/(sc*sp) if sc and sp else float('nan')
    print(f"\nPearson corr(min_conf, PER) = {corr:.2f}  (negative => low conf predicts high error)")

json.dump(summary, open(os.path.join(HERE,"results","normalized_summary.json"),"w"),
          ensure_ascii=False, indent=2)
print("\nwrote results/normalized_summary.json")
