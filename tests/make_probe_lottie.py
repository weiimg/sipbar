# -*- coding: utf-8 -*-
"""產生探測用的 Lottie：一杯水，時間軸往前推 = 水位下降。

Phase 0 只需要「載入任一 Lottie」，但用玩具檔量出來的耗時會過度樂觀。
所以這裡刻意做成有代表性的複雜度：外框描邊 + 遮罩 + 漸層填色 + 氣泡，
再另外做一個「重量級」版本（更多圖層）當上限參考。
"""
import json
import os

W = H = 120
FR = 60
FRAMES = 60

# 杯子內部：x 30..90、y 24..100
CUP_W, CUP_H = 60, 76
CUP_CX, CUP_CY = 60, 62
WATER_FULL_CY = 24 + 50      # 水面貼齊杯口
WATER_EMPTY_CY = 24 + 126    # 水面掉到杯底之下


def v(k):
    return {"a": 0, "k": k}


def kf(pairs, linear=False):
    """pairs: [(frame, value), ...]

    linear=False 用 easeInOut——播起來好看，但**停在中間某一幀時讀不準**：
    實測時間軸 30% 的位置水其實還有 89%。這正是「為了播一次而設計」的素材通病。
    linear=True 讓時間軸位置直接等於水位，適合被當進度條刷。
    """
    out = []
    for i, (t, s) in enumerate(pairs):
        node = {"t": t, "s": s if isinstance(s, list) else [s]}
        if i < len(pairs) - 1:
            if linear:
                # 線性要給對角線上的控制點。**不能只是把 i/o 拿掉**——
                # 沒有 handle 的 keyframe 在 rlottie 是「保持」，整段動畫會靜止不動，
                # 而且不會報錯，只會得到一張不會變的圖。
                node["i"] = {"x": [1.0], "y": [1.0]}
                node["o"] = {"x": [0.0], "y": [0.0]}
            else:
                node["i"] = {"x": [0.42], "y": [1.0]}
                node["o"] = {"x": [0.58], "y": [0.0]}
        out.append(node)
    return {"a": 1, "k": out}


def tr(p=(0, 0), o=100):
    return {"ty": "tr", "p": v(list(p)), "a": v([0, 0]), "s": v([100, 100]),
            "r": v(0), "o": v(o), "sk": v(0), "sa": v(0)}


def group(items, name="g"):
    return {"ty": "gr", "nm": name, "np": len(items), "it": items, "hd": False}


def layer(ind, name, shapes, ip=0, op=FRAMES, td=None, tt=None, ks=None):
    L = {
        "ddd": 0, "ind": ind, "ty": 4, "nm": name, "sr": 1,
        "ks": ks or {"o": v(100), "r": v(0), "p": v([0, 0, 0]),
                     "a": v([0, 0, 0]), "s": v([100, 100, 100])},
        "ao": 0, "shapes": shapes, "ip": ip, "op": op, "st": 0, "bm": 0,
    }
    if td is not None:
        L["td"] = td
    if tt is not None:
        L["tt"] = tt
    return L


def cup_outline():
    return layer(1, "cup-outline", [group([
        {"ty": "rc", "d": 1, "s": v([CUP_W, CUP_H]), "p": v([CUP_CX, CUP_CY]), "r": v(10)},
        {"ty": "st", "c": v([0.92, 0.94, 0.98, 1]), "o": v(88), "w": v(4),
         "lc": 2, "lj": 2, "ml": 4},
        tr(),
    ], "outline")])


def cup_matte():
    return layer(2, "cup-matte", [group([
        {"ty": "rc", "d": 1, "s": v([CUP_W - 4, CUP_H - 4]), "p": v([CUP_CX, CUP_CY]), "r": v(8)},
        {"ty": "fl", "c": v([1, 1, 1, 1]), "o": v(100), "r": 1},
        tr(),
    ], "matte")], td=1)


def water_body(bubbles=3, linear=False):
    items = [group([
        {"ty": "rc", "d": 1, "s": v([CUP_W + 24, 100]),
         "p": kf([(0, [CUP_CX, WATER_FULL_CY]), (FRAMES, [CUP_CX, WATER_EMPTY_CY])],
                 linear=linear),
         "r": v(0)},
        # 漸層填色：真素材幾乎都有，純色會低估耗時
        {"ty": "gf", "o": v(100), "r": 1, "t": 1,
         "s": v([CUP_CX, 24]), "e": v([CUP_CX, 100]),
         "g": {"p": 3, "k": v([0.0, 0.42, 0.72, 0.95,
                               0.5, 0.31, 0.66, 0.91,
                               1.0, 0.18, 0.48, 0.78])},
         "h": v(0), "a": v(0)},
        tr(),
    ], "water")]
    for i in range(bubbles):
        x = 44 + i * 16
        items.append(group([
            {"ty": "el", "d": 1, "s": v([5 - i * 0.6, 5 - i * 0.6]), "p": v([0, 0])},
            {"ty": "fl", "c": v([1, 1, 1, 1]), "o": v(52), "r": 1},
            {"ty": "tr", "p": kf([(0, [x, 92]), (FRAMES, [x, 34])]),
             "a": v([0, 0]), "s": v([100, 100]), "r": v(0),
             "o": kf([(0, 0), (FRAMES // 3, 70), (FRAMES, 0)]),
             "sk": v(0), "sa": v(0)},
        ], f"bubble{i}"))
    return layer(3, "water", items, tt=1)


def build(bubbles=3, extra_layers=0, linear=False):
    layers = [cup_outline(), cup_matte(), water_body(bubbles, linear)]
    for n in range(extra_layers):
        layers.append(layer(10 + n, f"deco{n}", [group([
            {"ty": "el", "d": 1, "s": v([14, 14]), "p": v([0, 0])},
            {"ty": "st", "c": v([0.4, 0.7, 0.95, 1]), "o": v(40), "w": v(2), "lc": 2, "lj": 2},
            {"ty": "tr", "p": kf([(0, [20 + n * 7, 20]), (FRAMES, [100 - n * 7, 100])]),
             "a": v([0, 0]), "s": v([100, 100]), "r": kf([(0, 0), (FRAMES, 180)]),
             "o": v(60), "sk": v(0), "sa": v(0)},
        ], f"deco{n}")]))
    return {
        "v": "5.7.4", "fr": FR, "ip": 0, "op": FRAMES, "w": W, "h": H,
        "nm": "water-probe", "ddd": 0, "assets": [], "layers": layers,
    }


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    for name, kwargs in (("water_probe.json", {}),
                         ("water_heavy.json", {"bubbles": 8, "extra_layers": 10}),
                         ("water_linear.json", {"linear": True})):
        path = os.path.join(here, name)
        with open(path, "w", encoding="utf-8") as f:
            # 一定要 indent。壓成一行的話整個檔案就是一條 1.8 萬字元的長行，
            # 編輯器與語法高亮會當場卡死或崩潰——實際害使用者的 app 跳掉過一次。
            json.dump(build(**kwargs), f, ensure_ascii=False, indent=1)
            f.write("\n")
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        print(f"{name}: {os.path.getsize(path) / 1024:.1f} KB, "
              f"{len(build(**kwargs)['layers'])} 圖層, "
              f"{len(lines)} 行, 最長行 {max(len(x) for x in lines)} 字元")
