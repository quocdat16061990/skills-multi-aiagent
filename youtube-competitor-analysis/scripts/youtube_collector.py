"""Public, unauthenticated YouTube collector. No bypass or cookies."""
from __future__ import annotations
import json,os,re,shutil,subprocess
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
import requests

UA="Mozilla/5.0 (compatible; public-metadata-research/1.0)"

def validate_url(url):
    p=urlparse(url)
    if p.scheme not in ("http","https") or p.netloc.lower() not in ("youtube.com","www.youtube.com","m.youtube.com"):
        raise ValueError("URL phải là URL YouTube channel công khai")
    if not p.path or p.path=="/": raise ValueError("Thiếu đường dẫn channel")
    return url.rstrip("/")

def parse_int(v):
    if isinstance(v,(int,float)): return int(v)
    if not v:return None
    s=str(v).replace(",","")
    m=re.search(r"([\d.]+)\s*([KMB]?)",s,re.I)
    if not m:return None
    return int(float(m.group(1))*{"":1,"K":1e3,"M":1e6,"B":1e9}[m.group(2).upper()])

def duration_seconds(v):
    if isinstance(v,(int,float)):return int(v)
    if not v:return None
    parts=str(v).split(":")
    try:
        n=0
        for x in parts:n=n*60+int(x)
        return n
    except ValueError:return None

def absolute_date(text):
    if not text:return (None,False)
    s=str(text).strip()
    for fmt in ("%Y%m%d","%Y-%m-%d","%b %d, %Y","%B %d, %Y"):
        try:return (datetime.strptime(s,fmt).date().isoformat(),True)
        except ValueError:pass
    return (s,False)

def _yt_dlp_binary():
    configured=os.environ.get("YT_DLP_BIN")
    if configured and Path(configured).is_file(): return configured
    found=shutil.which("yt-dlp")
    if found:return found
    skill_dir=Path(__file__).resolve().parent.parent
    runtime_root=Path(os.environ.get("OPENCLAW_RUNTIME_ROOT") or skill_dir/"../../../..").resolve()
    for candidate in (runtime_root/".local/bin/yt-dlp",runtime_root/".openclaw/tools/document-venv/bin/yt-dlp"):
        if candidate.is_file() and os.access(candidate,os.X_OK):return str(candidate)
    return None

def _yt_dlp(binary,url,limit):
    cmd=[binary,"--dump-single-json","--flat-playlist","--playlist-end",str(limit),"--no-warnings",url]
    env=os.environ.copy()
    resolved=Path(binary).resolve()
    if resolved.parent.name=="bin" and resolved.parent.parent.name==".local":
        env["PYTHONUSERBASE"]=str(resolved.parent.parent)
    cp=subprocess.run(cmd,capture_output=True,text=True,timeout=120,env=env)
    if cp.returncode: raise RuntimeError(cp.stderr.strip() or "yt-dlp thất bại")
    d=json.loads(cp.stdout); ch={"title":d.get("channel") or d.get("uploader") or d.get("title") or "N/A","handle":d.get("channel_id") or d.get("uploader_id") or "N/A","subscribers":parse_int(d.get("channel_follower_count")),"url":url}
    out=[]
    for x in (d.get("entries") or [])[:limit]:
        date,certain=absolute_date(x.get("upload_date") or x.get("release_date"))
        vid=x.get("id"); typ="short" if "/shorts/" in str(x.get("url") or "") else "unknown"
        out.append({"video_id":vid,"title":x.get("title") or "N/A","url":x.get("webpage_url") or (f"https://www.youtube.com/watch?v={vid}" if vid else "N/A"),"views":parse_int(x.get("view_count")),"published":date or x.get("timestamp") or "N/A","published_certain":certain,"duration":duration_seconds(x.get("duration")),"type":typ})
    return ch,out

def _extract_json(html,marker="ytInitialData"):
    pos=html.find(marker)
    if pos<0:raise RuntimeError("Không tìm thấy ytInitialData")
    start=html.find("{",pos); depth=0; string=False; esc=False
    for i in range(start,len(html)):
        c=html[i]
        if string:
            if esc:esc=False
            elif c=="\\":esc=True
            elif c=='"':string=False
        else:
            if c=='"':string=True
            elif c=="{":depth+=1
            elif c=="}":
                depth-=1
                if depth==0:return json.loads(html[start:i+1])
    raise RuntimeError("ytInitialData không hoàn chỉnh")
def _text(x):
    if not x:return None
    return x.get("simpleText") or "".join(y.get("text","") for y in x.get("runs",[]))
def _walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values():yield from _walk(v)
    elif isinstance(x,list):
        for v in x:yield from _walk(v)
def _html(url,limit):
    r=requests.get(url,headers={"User-Agent":UA,"Accept-Language":"en-US,en;q=0.8"},timeout=30)
    if r.status_code in (403,429):raise RuntimeError(f"YouTube chặn truy cập HTTP {r.status_code}; không thử vượt chặn")
    r.raise_for_status(); data=_extract_json(r.text)
    title="N/A"; handle="N/A"; subs=None; videos=[]; seen=set()
    for n in _walk(data):
        md=n.get("channelMetadataRenderer")
        if md:title=md.get("title") or title; handle=md.get("vanityChannelUrl") or handle
        vh=n.get("videoRenderer") or n.get("gridVideoRenderer") or n.get("reelItemRenderer")
        if not vh:continue
        vid=vh.get("videoId");
        if not vid or vid in seen:continue
        seen.add(vid); rel=_text(vh.get("publishedTimeText")) or "N/A"; dur=duration_seconds(_text(vh.get("lengthText")))
        short=bool(n.get("reelItemRenderer")) or (dur is not None and dur<=60 and "/shorts" in url)
        videos.append({"video_id":vid,"title":_text(vh.get("title")) or _text(vh.get("headline")) or "N/A","url":f"https://www.youtube.com/{'shorts/' if short else 'watch?v='}{vid}","views":parse_int(_text(vh.get("viewCountText"))),"published":rel,"published_certain":False,"duration":dur,"type":"short" if short else "unknown"})
        if len(videos)>=limit:break
    return {"title":title,"handle":handle,"subscribers":subs,"url":url},videos

def collect_channel(url,limit):
    url=validate_url(url); warnings=[]
    binary=_yt_dlp_binary()
    if binary:
        try:ch,vids=_yt_dlp(binary,url,limit); return {"channel":ch,"videos":vids,"source":"yt-dlp","warnings":warnings}
        except Exception as e:warnings.append(f"yt-dlp: {e}")
    ch,vids=_html(url,limit)
    if not vids:warnings.append("Không tìm thấy video công khai trong HTML ban đầu; trang có thể yêu cầu continuation/API")
    return {"channel":ch,"videos":vids,"source":"ytInitialData","warnings":warnings}
