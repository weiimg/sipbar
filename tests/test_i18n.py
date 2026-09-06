# -*- coding: utf-8 -*-
"""驗證 i18n 翻譯的完整性：兩邊字典的 key 必須對齊。

新增字串時只加了 _ZH 忘了 _EN（或反過來），t() 會 fallback 到中文，
英文介面就會混進中文——不會炸，但使用者會看到亂的。這支測試擋的就是這件事。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import i18n  # noqa: E402

fails = []

zh_keys = set(i18n._ZH.keys())
en_keys = set(i18n._EN.keys())

missing_en = sorted(zh_keys - en_keys)
missing_zh = sorted(en_keys - zh_keys)

if missing_en:
    fails.append(f"_ZH 有但 _EN 沒有（{len(missing_en)} 個）：")
    for k in missing_en:
        fails.append(f"  {k}")

if missing_zh:
    fails.append(f"_EN 有但 _ZH 沒有（{len(missing_zh)} 個）：")
    for k in missing_zh:
        fails.append(f"  {k}")

# 值的型別也要一致：一邊 str 另一邊 list 會讓 t()/tl() 拿到錯的東西。
for k in zh_keys & en_keys:
    zt, et = type(i18n._ZH[k]).__name__, type(i18n._EN[k]).__name__
    if zt != et:
        fails.append(f"  型別不符：{k}  _ZH={zt}  _EN={et}")

print(f"_ZH: {len(zh_keys)} 個 key")
print(f"_EN: {len(en_keys)} 個 key")

if fails:
    for line in fails:
        print(line)
    print(f"\n有 {len(missing_en)} 個缺英文、{len(missing_zh)} 個缺中文")
else:
    print("兩邊完全對齊")

sys.exit(1 if fails else 0)
