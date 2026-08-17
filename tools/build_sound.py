# -*- coding: utf-8 -*-
"""產生升級時的提示音 —— assets/sound/*.wav。

## 為什麼自己合成，不用現成音效

這個專案沒有一個外來的素材：字體是 build_font.py 產的，圖示是 make_icon.py
畫的，示意圖是程式排的。音效沒有理由破例——音效庫的檔案要帶授權、要標出處，
而且十有八九是為 app 通知設計的「叮」，跟一隻杯子的個性對不起來。

合成的另一個好處是可以調到剛剛好：音效庫給你的是固定的響度，
而這裡最重要的參數正是「不能太大聲」（見 PEAK）。

## 為什麼是 WAV

`winsound.PlaySound()` 只吃 PCM WAV。換成 mp3／ogg 就要帶解碼器
（QtMultimedia 是幾十 MB，而且這台機器上根本沒裝），為了一個提示音不值得。
未壓縮的代價是每個檔案幾十 KB，對一個 47MB 的發布包等於沒有。

## 為什麼是兩個音，一個上行一個下行

升級有兩級：忽略 15 分鐘變虛弱、40 分鐘倒地。同一個聲音響兩次，
第二次就沒有帶進任何新訊息。

    weak.wav       C6 -> E6    往上　一個問句的語調
    collapsed.wav  G5 -> D5    往下　而且更低更慢

上行是招呼，下行是倒下去。用同一種音色（同一組泛音、同一種衰減），
所以聽起來是同一個角色在講兩句話，不是兩個不相干的提示音。

## 音色

基音加兩個泛音，指數衰減，高次泛音衰減得更快——真實的物體都是這樣，
少了這一項聽起來就是合成器的正弦波。結果接近敲一下玻璃杯。

用法：python tools/build_sound.py
"""
import array
import math
import os
import sys
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "assets", "sound")

SR = 44100                  # 取樣率。泛音最高到 4kHz，這個值綽綽有餘
TAU = 2 * math.pi

# 尖峰振幅，滿刻度的比例。**這是唯一能控制音量的地方**——winsound 用系統音量
# 播放，程式沒有辦法在播放時調小。所以檔案本身就要是小聲的。
#
# 0.26 是刻意壓低的：這個聲音出現的時機是「已經被忽略 15 分鐘」，
# 它要做的是讓人注意到，不是嚇人一跳。被嚇到的人第一件事是去把它關掉，
# 那就等於這個功能不存在。
PEAK = 0.26

ATTACK_S = 0.006            # 起音斜坡。正弦從非零斜率開始會「喀」一聲
FADE_S = 0.010              # 尾端拉回零，同樣是為了不要有截斷的爆音

# (檔名, [(起始秒, 頻率, 長度, 衰減時間常數, 音量)])
VOICES = {
    # 往上的大三度。招呼的語調，不是警報。
    "weak": [
        (0.000, 1046.5, 0.45, 0.13, 1.00),      # C6
        (0.115, 1318.5, 0.50, 0.15, 0.90),      # E6
    ],
    # 往下的完全四度，比上面低一個八度，而且拖得更長。
    # 音高往下走是這個聲音的全部意思：它倒下去了。
    "collapsed": [
        (0.000, 784.0, 0.55, 0.17, 1.00),       # G5
        (0.155, 587.3, 0.70, 0.22, 1.00),       # D5
    ],
}


def ping(buf, start, freq, dur, tau, gain):
    """把一顆聲音疊進緩衝區。基音 + 二次 + 三次泛音，各自指數衰減。"""
    n0 = int(start * SR)
    n = int(dur * SR)
    atk = max(1, int(ATTACK_S * SR))
    fade = max(1, int(FADE_S * SR))
    for i in range(n):
        t = i / SR
        env = math.exp(-t / tau)
        if i < atk:
            env *= i / atk                      # 起音
        if i > n - fade:
            env *= (n - i) / fade               # 收尾
        s = (math.sin(TAU * freq * t)
             + 0.30 * math.sin(TAU * 2 * freq * t) * math.exp(-t / (tau * 0.50))
             + 0.10 * math.sin(TAU * 3 * freq * t) * math.exp(-t / (tau * 0.33)))
        buf[n0 + i] += s * gain * env


def render(notes):
    """把一組音符算成 int16 的樣本。"""
    total = max(start + dur for start, _, dur, _, _ in notes)
    buf = [0.0] * (int(total * SR) + 1)
    for start, freq, dur, tau, gain in notes:
        ping(buf, start, freq, dur, tau, gain)

    # 疊起來之後才正規化。先各自壓到 PEAK 再相加的話，重疊的那一段會超過。
    top = max(abs(v) for v in buf) or 1.0
    scale = PEAK * 32767 / top
    out = array.array("h", (int(v * scale) for v in buf))
    if sys.byteorder == "big":
        out.byteswap()                          # WAV 是小端序
    return out


def write(name, samples):
    path = os.path.join(OUT_DIR, name + ".wav")
    with wave.open(path, "wb") as f:
        f.setnchannels(1)                       # 單聲道。提示音沒有左右
        f.setsampwidth(2)                       # 16-bit PCM
        f.setframerate(SR)
        f.writeframes(samples.tobytes())
    return path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, notes in VOICES.items():
        samples = render(notes)
        path = write(name, samples)
        peak = max(abs(v) for v in samples) / 32767
        print(f"{path}")
        print(f"  {len(samples) / SR:.2f} 秒　尖峰 {peak:.2f}　"
              f"{os.path.getsize(path) / 1024:.0f}KB")


if __name__ == "__main__":
    main()
