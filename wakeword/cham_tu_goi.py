"""Chấm mô hình từ gọi .tflite bằng pyopen_wakeword — đúng thư viện wyoming-openwakeword 2.x dùng.

    python cham_tu_goi.py tro_ly.tflite ban_ghi.wav [ban_ghi_2.pcm ...]
"""
import sys, wave, numpy as np
from pyopen_wakeword import OpenWakeWord, OpenWakeWordFeatures
mh = sys.argv[1]
for tep in sys.argv[2:]:
    ww = OpenWakeWord.from_model(mh)
    f = OpenWakeWordFeatures.from_builtin()
    if tep.endswith(".wav"):
        w = wave.open(tep); pcm = w.readframes(w.getnframes())
        x = np.frombuffer(pcm, np.int16)
        nen = (np.random.default_rng(0).standard_normal(24000) * 30).astype(np.int16)
        pcm = np.concatenate([nen, x, nen[:8000]]).tobytes()
    else:
        pcm = open(tep, "rb").read(); pcm = pcm[:len(pcm)//2*2]
    diem = []
    for i in range(0, len(pcm), 2560):
        for emb in f.process_streaming(pcm[i:i+2560]):
            for p in ww.process_streaming(emb):
                diem.append((i / 32000, float(p)))
    d = [p for _, p in diem]
    dinh = []
    for t, p in diem:
        if p >= 0.95 and (not dinh or t - dinh[-1] > 1.5):
            dinh.append(round(t, 1))
    print(tep.split("/")[-1], f"max {max(d):.2f}", "@0.95:", dinh[:10])
