"""
Reverse proxy for Facebook — strips X-Frame-Options so FB can be
embedded in an <iframe> inside the app.
Cookies are loaded from the account's saved Playwright session.
"""
import asyncio
import json
import logging
import re
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/browser", tags=["browser"])

SESSIONS_DIR = Path(__file__).parent.parent / "data" / "sessions"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "max-age=0",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Connection": "keep-alive",
}

_STRIP = {
    "x-frame-options",
    "content-security-policy",
    "content-security-policy-report-only",
    "x-content-type-options",
    "cross-origin-opener-policy",
    "cross-origin-embedder-policy",
    "cross-origin-resource-policy",
    "strict-transport-security",
    "content-encoding",
    "transfer-encoding",
    "content-length",
}


def _load_cookies(account_id: str) -> list:
    """Return raw cookie list from Playwright session file."""
    sf = SESSIONS_DIR / f"{account_id}.json"
    if not sf.exists():
        logger.warning("[Proxy] Session file không tồn tại: %s", sf)
        return []
    try:
        data = json.loads(sf.read_text(encoding="utf-8"))
        cookies = [
            c for c in data.get("cookies", [])
            if "facebook.com" in c.get("domain", "")
        ]
        logger.info(
            "[Proxy] Loaded %d cookies cho %s: %s",
            len(cookies),
            account_id,
            [c["name"] for c in cookies],
        )
        return cookies
    except Exception as e:
        logger.error("[Proxy] Lỗi đọc session: %s", e)
        return []


_FB_DOMAINS = {"facebook.com", "messenger.com", "instagram.com"}
_CDN_SKIP = {"fbcdn.net", "cdninstagram.com", "akamaihd.net"}


def _is_proxiable(netloc: str) -> bool:
    return any(netloc == d or netloc.endswith("." + d) for d in _FB_DOMAINS) and \
           not any(netloc == d or netloc.endswith("." + d) for d in _CDN_SKIP)


def _to_mobile(url: str) -> str:
    """www.facebook.com / messenger.com → m.facebook.com."""
    url = url.replace("://www.facebook.com", "://m.facebook.com", 1)
    # messenger.com/t/xxx → m.facebook.com/messages/t/xxx
    if "://messenger.com" in url or "://www.messenger.com" in url:
        url = re.sub(r'https?://(www\.)?messenger\.com', 'https://m.facebook.com', url)
        # /t/thread → /messages/t/thread
        if "/messages/" not in url:
            url = url.replace("m.facebook.com/t/", "m.facebook.com/messages/t/", 1)
    return url


def _proxy_href(url: str, account_id: str, base_url: str) -> str:
    if not url:
        return url
    if url.startswith(("data:", "javascript:", "#", "mailto:")):
        return url
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/") and not url.startswith("/api/browser/"):
        url = "https://m.facebook.com" + url
    elif not url.startswith("http"):
        url = urljoin(base_url, url)
    url = _to_mobile(url)
    parsed = urlparse(url)
    if _is_proxiable(parsed.netloc):
        return f"/api/browser/proxy?account_id={account_id}&url={quote(url, safe='')}"
    return url


def _rewrite_html(html: str, account_id: str, page_url: str) -> str:
    def sub_href(m):
        q = m.group(1)
        val = m.group(2)
        return f'href={q}{_proxy_href(val, account_id, page_url)}{q}'

    def sub_action(m):
        q = m.group(1)
        val = m.group(2)
        return f'action={q}{_proxy_href(val, account_id, page_url)}{q}'

    def sub_meta_refresh(m):
        tag = m.group(0)

        def fix_url(cm):
            return cm.group(1) + _proxy_href(
                cm.group(2), account_id, page_url
            )

        return re.sub(r'(url=)([^\s"\'>;,&]+)', fix_url, tag, flags=re.I)

    html = re.sub(r'href=(["\'])([^"\']*)\1', sub_href, html)
    html = re.sub(r'action=(["\'])([^"\']*)\1', sub_action, html)
    # Rewrite <meta http-equiv="refresh" content="0; url=..."> so FB redirects stay in proxy
    html = re.sub(
        r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]*>',
        sub_meta_refresh, html, flags=re.I
    )

    inject = f"""<script>
(function(){{
  var AID='{account_id}';
  var PFX='/api/browser/proxy?account_id='+AID+'&url=';
  var PROXY_DOMAINS=['facebook.com','messenger.com'];
  var CDN_SKIP=['fbcdn.net','cdninstagram.com'];
  function shouldProxy(hostname){{
    var skip=CDN_SKIP.some(function(d){{return hostname===d||hostname.endsWith('.'+d);}});
    if(skip) return false;
    return PROXY_DOMAINS.some(function(d){{return hostname===d||hostname.endsWith('.'+d);}});
  }}
  function toMobile(u){{
    u=u.replace('://www.facebook.com','://m.facebook.com');
    u=u.replace(/https?:\\/\\/(www\\.)?messenger\\.com/,'https://m.facebook.com');
    return u;
  }}
  function px(u){{
    if(!u||typeof u!=='string') return u;
    if(/^(data:|javascript:|#|mailto:)/.test(u)) return u;
    if(u.startsWith('/api/browser/')) return u;
    if(u.startsWith('//')) u='https:'+u;
    if(u.startsWith('/')) u='https://m.facebook.com'+u;
    if(!u.startsWith('http')) return u;
    u=toMobile(u);
    try{{
      if(shouldProxy(new URL(u).hostname)) return PFX+encodeURIComponent(u);
    }}catch(e){{}}
    return u;
  }}
  // --- history.pushState / replaceState ---
  // Intercept so FB's SPA navigation doesn't change iframe URL to a React route
  (function(){{
    function wrapHistory(name){{
      var orig=history[name];
      if(!orig) return;
      history[name]=function(state,title,url){{
        if(url&&typeof url==='string'&&url!==''&&!url.startsWith('#')&&!url.startsWith('/api/browser/')){{
          if(url.startsWith('/')) url=PFX+encodeURIComponent('https://m.facebook.com'+url);
          else if(url.startsWith('http')) url=px(url);
        }}
        return orig.call(this,state,title,url);
      }};
    }}
    try{{wrapHistory('pushState');}}catch(e){{}}
    try{{wrapHistory('replaceState');}}catch(e){{}}
  }})();
  // --- fetch ---
  var oFetch=window.fetch;
  window.fetch=function(inp,init){{
    if(typeof inp==='string') inp=px(inp);
    else if(inp&&inp.url) inp=new Request(px(inp.url),inp);
    return oFetch(inp,init);
  }};
  // --- XHR ---
  var oOpen=XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open=function(m,u){{
    return oOpen.apply(this,[m,px(u)].concat(Array.prototype.slice.call(arguments,2)));
  }};
  // --- location.assign ---
  try{{
    var oAssign=Location.prototype.assign;
    Location.prototype.assign=function(u){{ oAssign.call(this,px(String(u))); }};
  }}catch(e){{}}
  // --- location.replace ---
  try{{
    var oReplace=Location.prototype.replace;
    Location.prototype.replace=function(u){{ oReplace.call(this,px(String(u))); }};
  }}catch(e){{}}
  // --- location.href setter ---
  try{{
    var oHrefDesc=Object.getOwnPropertyDescriptor(Location.prototype,'href');
    if(oHrefDesc&&oHrefDesc.set){{
      var origHrefSet=oHrefDesc.set;
      Object.defineProperty(Location.prototype,'href',{{
        get:oHrefDesc.get,
        set:function(u){{ origHrefSet.call(this,px(String(u))); }},
        configurable:true
      }});
    }}
  }}catch(e){{}}
  // --- window.open ---
  try{{
    var oWinOpen=window.open;
    window.open=function(u,n,f){{ return oWinOpen.call(window,u?px(String(u)):u,n,f); }};
  }}catch(e){{}}
  // --- dynamic link click interception ---
  document.addEventListener('click',function(e){{
    var a=e.target.closest('a[href]');
    if(!a) return;
    var href=a.getAttribute('href');
    if(!href||href.startsWith('#')||href.startsWith('javascript:')||href.startsWith('mailto:')||href.startsWith('/api/')) return;
    var newUrl=px(href);
    if(newUrl!==href){{
      e.preventDefault();
      e.stopPropagation();
      window.location.assign(newUrl);
    }}
  }},true);
  // --- form submit interception ---
  document.addEventListener('submit',function(e){{
    var form=e.target;
    if(!form||!form.action) return;
    var newAction=px(form.action);
    if(newAction!==form.action){{
      form.action=newAction;
    }}
  }},true);
}})();
</script>"""

    if "<head>" in html:
        html = html.replace("<head>", "<head>" + inject, 1)
    else:
        html = inject + html
    return html


def _clean_headers(resp_headers) -> dict:
    out = {}
    for k, v in resp_headers.items():
        if k.lower() not in _STRIP:
            out[k] = v
    return out


# FB-specific request headers that must be forwarded for API/GraphQL calls to work
_FB_PASSTHROUGH_HEADERS = {
    "x-fb-lsd",          # CSRF token – required by Graph/BanzaiAPI
    "x-asbd-id",         # App-session binding
    "x-fb-friendly-name",
    "x-fb-connection-token",
    "x-fb-connection-quality",
    "x-fb-sim-hni",
    "viewport-width",
    "dpr",
}


async def _fetch(
    method: str,
    url: str,
    cookie_list: list,
    body: bytes | None = None,
    content_type: str = "",
    extra_headers: dict | None = None,
):
    import requests as req
    loop = asyncio.get_event_loop()

    def _do():
        s = req.Session()
        for c in cookie_list:
            s.cookies.set(
                c["name"],
                c["value"],
                domain=c.get("domain", ".facebook.com"),
                path=c.get("path", "/"),
            )
        h = dict(_HEADERS)
        h["Referer"] = "https://m.facebook.com/"
        if content_type:
            h["Content-Type"] = content_type
        if method == "POST":
            h["Origin"] = "https://m.facebook.com"
            h["Sec-Fetch-Mode"] = "cors"
            h["Sec-Fetch-Site"] = "same-origin"
        # Forward FB-specific headers sent by the in-page JavaScript
        if extra_headers:
            h.update(extra_headers)
        resp = s.request(
            method,
            url,
            data=body if method == "POST" else None,
            headers=h,
            timeout=30,
            allow_redirects=True,
        )
        logger.info(
            "[Proxy] %s %s → %d | len=%d",
            method, url[:80], resp.status_code, len(resp.content),
        )
        return resp

    return await loop.run_in_executor(None, _do)


# ── Routes ────────────────────────────────────────────────

@router.get("/proxy")
@router.post("/proxy")
async def fb_proxy(
    request: Request,
    url: str = Query(...),
    account_id: str = Query(...),
):
    cookie_list = _load_cookies(account_id)
    if not cookie_list:
        html = (
            "<html><body style='font-family:sans-serif;padding:40px'>"
            "<h3>Chưa có session cho tài khoản này.</h3>"
            "<p>Hãy đăng bài 1 lần (chọn 'Hiện trình duyệt') để lưu cookie trước.</p>"
            "</body></html>"
        )
        return Response(content=html, media_type="text/html")

    # Always use mobile site — server-rendered HTML, no SPA/GraphQL issues
    url = _to_mobile(url)

    body = await request.body() if request.method == "POST" else None
    ctype = request.headers.get("content-type", "")

    # Forward FB-specific headers (CSRF, app-session) sent by page JS
    extra_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() in _FB_PASSTHROUGH_HEADERS
    }

    try:
        resp = await _fetch(
            request.method, url, cookie_list, body, ctype, extra_headers
        )
    except Exception as e:
        logger.error("[Proxy] %s %s → %s", request.method, url, e)
        return Response(
            content=f"<html><body><h3>Lỗi: {e}</h3></body></html>",
            media_type="text/html",
            status_code=502,
        )

    ctype = resp.headers.get("content-type", "")
    clean_h = _clean_headers(resp.headers)

    if "text/html" in ctype:
        rewritten = _rewrite_html(resp.text, account_id, url)
        return Response(
            content=rewritten.encode("utf-8", errors="replace"),
            media_type="text/html; charset=utf-8",
            headers=clean_h,
            status_code=resp.status_code,
        )

    return Response(
        content=resp.content,
        media_type=ctype or "application/octet-stream",
        headers=clean_h,
        status_code=resp.status_code,
    )
