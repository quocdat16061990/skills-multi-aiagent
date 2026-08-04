"""Pure, test-friendly metric functions."""
from datetime import date
from statistics import mean,median

def views_per_day(row,today=None):
    if not row.get("published_certain") or row.get("views") is None:return None
    try:d=date.fromisoformat(row["published"])
    except (ValueError,TypeError):return None
    days=((today or date.today())-d).days
    return round(row["views"]/max(days,1),2) if days>=0 else None

def summarize(rows):
    vals=[r["views"] for r in rows if isinstance(r.get("views"),(int,float))]
    top=sorted(rows,key=lambda r:r.get("views") if isinstance(r.get("views"),(int,float)) else -1,reverse=True)[:10]
    return {"count":len(rows),"total":sum(vals),"mean":round(mean(vals),2) if vals else None,"median":round(median(vals),2) if vals else None,"min":min(vals) if vals else None,"max":max(vals) if vals else None,"top_video_ids":[r.get("video_id") for r in top]}
def analyze(rows):
    for r in rows:r["views_per_day"]=views_per_day(r)
    return {"all":summarize(rows),"shorts":summarize([r for r in rows if r.get("type")=="short"]),"long_form":summarize([r for r in rows if r.get("type")=="long-form"]),"unknown":summarize([r for r in rows if r.get("type")=="unknown"])}
