"""以音訊波形校正剪點。Whisper 的詞時間戳常有 0.1～0.4 秒誤差，直接拿來剪會吃字或剪不到。

做法：
  1. 讀 16kHz 單聲道 wav，算每 10ms 的 RMS 能量
  2. 用自適應門檻找出「真實靜音區間」
  3. 剪點貼齊到最近的真實靜音處；若附近沒有靜音（連續語流中），貼齊到能量最低的地方
"""
import array, math, wave

FRAME = 0.01  # 秒


def load_rms(path):
    w = wave.open(str(path))
    if w.getnchannels() != 1 or w.getsampwidth() != 2:
        raise ValueError("需要 16-bit 單聲道 wav（transcribe_zh.py 產生的 audio.wav 即可）")
    sr = w.getframerate()
    data = array.array("h")
    data.frombytes(w.readframes(w.getnframes()))
    n = int(sr * FRAME)
    return [math.sqrt(sum(x * x for x in data[i : i + n]) / n) for i in range(0, len(data) - n, n)]


def threshold(rms, override=None):
    """門檻 = 底噪的 2.5 倍，且不低於 80。底噪取能量最低 10% 的平均。"""
    if override:
        return override
    s = sorted(rms)
    low = s[: max(1, len(s) // 10)]
    return max(80.0, 2.5 * (sum(low) / len(low)))


def silences(rms, thr, min_len=0.12):
    """回傳 [(start, end)] 真實靜音區間（秒）。"""
    out, start = [], None
    for i, r in enumerate(rms):
        if r < thr and start is None:
            start = i
        elif r >= thr and start is not None:
            if (i - start) * FRAME >= min_len:
                out.append((start * FRAME, i * FRAME))
            start = None
    if start is not None and (len(rms) - start) * FRAME >= min_len:
        out.append((start * FRAME, len(rms) * FRAME))
    return out


def snap(t, rms, sils, window=0.3, inset=0.03, dip=0.12):
    """把時間 t 貼齊到最近的真實靜音處。回傳 (新時間, 方式)。"""
    best, best_d = None, None
    for s, e in sils:
        if e < t - window or s > t + window:
            continue
        d = 0.0 if s <= t <= e else min(abs(t - s), abs(t - e))
        if best_d is None or d < best_d:
            best, best_d = (s, e), d
    if best:
        s, e = best
        lo, hi = s + inset, e - inset
        if hi <= lo:
            return (s + e) / 2, "silence"
        return min(max(t, lo), hi), "silence"
    # 連續語流：找 ±dip 秒內能量最低的 10ms
    a, b = max(0, int((t - dip) / FRAME)), min(len(rms) - 1, int((t + dip) / FRAME))
    if b <= a:
        return t, "none"
    i = min(range(a, b + 1), key=lambda k: rms[k])
    return i * FRAME + FRAME / 2, "dip"
