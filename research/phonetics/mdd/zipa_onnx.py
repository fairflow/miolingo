"""ZIPA-CR large CTC (ONNX) phone recognizer: wav (16 kHz float) -> log-probs, greedy IPA."""
import numpy as np, onnxruntime as ort, kaldi_native_fbank as knf

class Zipa:
    def __init__(self, model="/opt/zipa/model.fp16.onnx", tokens="/opt/zipa/tokens.txt"):
        so = ort.SessionOptions(); so.log_severity_level = 3
        self.s = ort.InferenceSession(model, so, providers=["CPUExecutionProvider"])
        self.id2tok = {}
        for line in open(tokens, encoding="utf-8"):
            t, i = line.rstrip("\n").rsplit(" ", 1); self.id2tok[int(i)] = t
        self.vocab = {t: i for i, t in self.id2tok.items()}

    def feats(self, x, sr=16000):
        o = knf.FbankOptions(); o.frame_opts.dither = 0; o.frame_opts.snip_edges = False
        o.frame_opts.samp_freq = sr; o.mel_opts.num_bins = 80
        f = knf.OnlineFbank(o); f.accept_waveform(sr, x.astype(np.float32).tolist()); f.input_finished()
        return np.stack([f.get_frame(i) for i in range(f.num_frames_ready)])

    def log_probs(self, x, sr=16000):
        F = self.feats(x, sr)[None].astype(np.float32)
        lp, n = self.s.run(None, {"x": F, "x_lens": np.array([F.shape[1]], dtype=np.int64)})
        return lp[0, : int(n[0])]          # (T', 127), ~25 frames/s? (subsampled)

    def greedy(self, lp):
        ids = lp.argmax(-1); out = []; prev = -1
        for i in ids:
            if i != prev and i != 0: out.append(self.id2tok[int(i)])
            prev = i
        return "".join(out).replace("▁", " ").strip()
