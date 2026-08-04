"""Deterministic keyword coding; labels always retain matching evidence."""
import json,re
DEFAULT={"topics":{"Hướng dẫn":["how to","cách","hướng dẫn"],"Đánh giá":["review","đánh giá"],"Tin tức":["news","tin tức","mới nhất"]},"hooks":{"Con số":r"\b\d+[x%]?\b","Câu hỏi":r"^(why|how|what|tại sao|làm sao|cách nào)\b","Khẩn cấp":r"\b(now|urgent|ngay|đừng bỏ lỡ)\b","Danh sách":r"\b(top|\d+ (ways|tips|cách|mẹo))\b"},"recommendations":{"top_n":10}}
def load_config(path=None):
    cfg=json.loads(json.dumps(DEFAULT))
    if path:
        with open(path,encoding="utf-8") as f:user=json.load(f)
        for k,v in user.items():
            if isinstance(v,dict) and isinstance(cfg.get(k),dict):cfg[k].update(v)
            else:cfg[k]=v
    return cfg
def classify(row,cfg):
    text=(row.get("title") or "").casefold(); topics=[]; topic_ev=[]
    for label,words in cfg.get("topics",{}).items():
        hits=[w for w in words if str(w).casefold() in text]
        if hits:topics.append(label); topic_ev.extend(hits)
    hooks=[]; hook_ev=[]
    for label,pattern in cfg.get("hooks",{}).items():
        m=re.search(pattern,text,re.I)
        if m:hooks.append(label); hook_ev.append(m.group(0))
    out=dict(row); out.update({"topics":topics or ["Khác/Chưa mã hóa"],"topic_evidence":topic_ev,"hooks":hooks,"hook_evidence":hook_ev,"coding_method":"deterministic-config"})
    if out.get("type")=="unknown" and out.get("duration") is not None:out["type"]="short" if out["duration"]<=60 else "long-form"
    return out
def classify_all(rows,cfg):return [classify(r,cfg) for r in rows]
