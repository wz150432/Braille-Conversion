"""GF 0019—2018 §12 的分词连写辅助。

jieba 只提供候选词界；规范原例、重叠词和词缀规则再校订候选结果。
语义/语节边界不能由普通分词器保证，出版前应使用 ChineseWord 接口校订。
"""

from functools import lru_cache

import jieba
from jieba.posseg import POSTokenizer


# §12.2.3 明列的语节/词界；避免把所有四字词一律截成 2+2。
_BOUNDARIES = {
    '中华人民共和国': ('中华', '人民', '共和国'),
    '环境保护规划': ('环境', '保护', '规划'),
    '无缝钢管': ('无缝', '钢管'), '生产关系': ('生产', '关系'),
    '劳动模范': ('劳动', '模范'), '特殊教育词典': ('特殊', '教育', '词典'),
    # §12.2.5 原例。
    '非业务人员': ('非业务', '人员'),
    # §12.2.6 原例中的内部词界。
    '浙赣线': ('浙赣', '线'), '京藏高速': ('京藏', '高速'),
}
_JOINED_WORDS = frozenset('''
阅读 晚会 地震 年轻 签名 示威 扭转 船只 但是 叮咛 芙蓉 巧克力 电视机 图书馆
全国 走来 胆小 环保 常用词 爱鸟周 吃得消 恶作剧 破天荒 一刀切 对不起
研究生院 高锰酸钾 古生物学家
人人 年年 看看 条条 来来往往 说说笑笑 清清楚楚 弯弯曲曲 千千万万
研究 雪白 通红
非业务 超声波 无条件 半导体 科学性 手工业者 乘务员 艺术家 拖拉机手 孩子们
八九天 十七八岁 中小学 陆海空军 沪宁杭 每年 山上 大红花
你的 他用 怎么样 慈爱 事业 地道 红十字会
'''.split())


@lru_cache(maxsize=1)
def _tokenizer():
    tokenizer = jieba.Tokenizer()
    for word in _JOINED_WORDS | _BOUNDARIES.keys():
        tokenizer.add_word(word, freq=100000)
    return POSTokenizer(tokenizer)


def _merge_short(left, right):
    """§12.1.3/12.2.5–6：仅合并有词性条件的紧密结构，不连接任意单字。"""
    a, af = left
    b, bf = right
    if len(b) == 1 and bf == 'k':
        return True
    if len(a) == 1 and af == 'h':
        return True
    if len(a + b) > 3:
        return False
    if len(a) == 1 and af.startswith('r'):
        return (len(b) == 1 and bf.startswith(('v', 'a', 'p'))) or b == '的'
    if a in ('很', '太', '更', '最') and bf.startswith('a'):
        return True
    if a in ('每', '各') and bf.startswith(('n', 't', 'q')):
        return True
    if bf == 'f' and af.startswith('n'):
        return True
    if af == 'm' and bf == 'q':
        return True
    return len(b) == 1 and b == '人' and af == 'ns'


@lru_cache(maxsize=2048)
def _segment(text):
    if text in _BOUNDARIES:
        return _BOUNDARIES[text]
    candidates = []
    for token in _tokenizer().cut(text, HMM=False):
        parts = _BOUNDARIES.get(token.word, (token.word,))
        # §12.2.4：ABAB 分写，AABB 连写。
        if len(token.word) == 4 and token.word[:2] == token.word[2:]:
            parts = (token.word[:2], token.word[2:])
        candidates.extend((part, token.flag) for part in parts)
    merged = []
    for item in candidates:
        if merged and _merge_short(merged[-1], item):
            a, af = merged.pop()
            merged.append((a + item[0], item[1] if af == 'h' else af))
        else:
            merged.append(item)
    return tuple(word for word, _ in merged)


def segment_chinese(text: str):
    """返回可校订的候选词列表。调用方应传入连续的中文字符段。"""
    return list(_segment(text)) if text else []
