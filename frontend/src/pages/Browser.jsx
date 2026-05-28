import { useCallback, useEffect, useRef, useState } from 'react'
import { getAccounts } from '../api'

const FB_HOME = 'https://m.facebook.com/'

const s = {
  wrap: {
    display: 'flex',
    flexDirection: 'column',
    height: 'calc(100vh - 48px)',
    gap: 10,
  },
  bar: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    background: '#fff',
    border: '1px solid #e4e6ea',
    borderRadius: 10,
    padding: '8px 14px',
    flexShrink: 0,
  },
  select: {
    padding: '6px 10px',
    borderRadius: 7,
    border: '1px solid #ddd',
    fontSize: 13,
    background: '#f7f8fa',
    minWidth: 220,
  },
  navBtn: {
    padding: '6px 12px',
    borderRadius: 7,
    border: '1px solid #ddd',
    background: '#f7f8fa',
    cursor: 'pointer',
    fontSize: 16,
    lineHeight: 1,
  },
  urlInput: {
    flex: 1,
    padding: '6px 12px',
    borderRadius: 7,
    border: '1px solid #ddd',
    fontSize: 13,
  },
  goBtn: {
    padding: '6px 14px',
    borderRadius: 7,
    border: 'none',
    background: '#1877f2',
    color: '#fff',
    fontWeight: 600,
    fontSize: 13,
    cursor: 'pointer',
  },
  frameWrap: {
    flex: 1,
    position: 'relative',
    minHeight: 0,
  },
  frame: {
    border: '1px solid #e4e6ea',
    borderRadius: 10,
    width: '100%',
    height: '100%',
    background: '#f0f2f5',
    display: 'block',
  },
  overlay: {
    position: 'absolute',
    inset: 0,
    background: '#f0f2f5',
    borderRadius: 10,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10,
    color: '#888',
    fontSize: 14,
    gap: 8,
    pointerEvents: 'none',
  },
  empty: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#aaa',
    fontSize: 15,
    border: '1px dashed #e4e6ea',
    borderRadius: 10,
  },
}

function makeProxyUrl(accountId, targetUrl) {
  return `/api/browser/proxy?account_id=${accountId}&url=${encodeURIComponent(targetUrl)}`
}

export default function Browser() {
  const [accounts, setAccounts] = useState([])
  const [accountId, setAccountId] = useState('')
  const [inputUrl, setInputUrl] = useState(FB_HOME)
  const [hasLoaded, setHasLoaded] = useState(false)
  const [overlayVisible, setOverlayVisible] = useState(false)
  const iframeRef = useRef(null)
  const overlayTimerRef = useRef(null)
  const accountIdRef = useRef(accountId)

  useEffect(() => {
    accountIdRef.current = accountId
  }, [accountId])

  useEffect(() => {
    getAccounts().then((r) => {
      setAccounts(r.data)
      if (r.data.length > 0) setAccountId(r.data[0].id)
    })
  }, [])

  // Show overlay with auto-fallback timeout so it never gets permanently stuck
  const showOverlay = useCallback(() => {
    clearTimeout(overlayTimerRef.current)
    setOverlayVisible(true)
    overlayTimerRef.current = setTimeout(() => setOverlayVisible(false), 10000)
  }, [])

  const hideOverlay = useCallback(() => {
    clearTimeout(overlayTimerRef.current)
    setOverlayVisible(false)
  }, [])

  // Always navigate the iframe directly – never rely on iframeSrc state diffing
  const loadSrc = useCallback((src) => {
    const frame = iframeRef.current
    if (!frame) return
    showOverlay()
    // Force reload even if src is the same (covers "already on home, click home again")
    if (frame.src === window.location.origin + src || frame.src === src) {
      frame.src = 'about:blank'
      requestAnimationFrame(() => {
        if (iframeRef.current) iframeRef.current.src = src
      })
    } else {
      frame.src = src
    }
  }, [showOverlay])

  // Load FB home when account changes
  useEffect(() => {
    if (!accountId) return
    setHasLoaded(true)
    setInputUrl(FB_HOME)
    loadSrc(makeProxyUrl(accountId, FB_HOME))
  }, [accountId, loadSrc])

  const navigate = useCallback((url) => {
    const aid = accountIdRef.current
    if (!aid) return
    let target = url.trim()
    if (!target.startsWith('http')) target = 'https://' + target
    setInputUrl(target)
    loadSrc(makeProxyUrl(aid, target))
  }, [loadSrc])

  const handleKey = (e) => {
    if (e.key === 'Enter') navigate(inputUrl)
  }

  // Detect if iframe escaped the proxy and redirect back.
  // Overlay stays until we confirm a proxy page loaded, hiding any React UI flash.
  const handleIframeLoad = useCallback(() => {
    const frame = iframeRef.current
    const aid = accountIdRef.current
    if (!frame || !aid) return
    try {
      const loc = frame.contentWindow.location.href
      // about:blank is our own temporary redirect – ignore it
      if (loc === 'about:blank') return
      if (!loc.includes('/api/browser/proxy')) {
        // Escaped proxy – show overlay and redirect back
        showOverlay()
        const isFb = /facebook\.com|messenger\.com/.test(loc)
        frame.src = makeProxyUrl(aid, isFb ? loc : FB_HOME)
      } else {
        // Proxy page confirmed – reveal and sync address bar
        hideOverlay()
        try {
          const fbUrl = new URL(loc).searchParams.get('url')
          if (fbUrl) setInputUrl(decodeURIComponent(fbUrl))
        } catch (_) {}
      }
    } catch (_) {
      // Cross-origin: iframe navigated directly to FB – redirect back
      showOverlay()
      frame.src = makeProxyUrl(aid, FB_HOME)
    }
  }, [showOverlay, hideOverlay])

  return (
    <div style={s.wrap}>
      <div style={s.bar}>
        <select
          value={accountId}
          onChange={(e) => setAccountId(e.target.value)}
          style={s.select}
        >
          <option value="">-- Chọn tài khoản --</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.email}
            </option>
          ))}
        </select>

        <button style={s.navBtn} title="Về trang chủ FB"
          onClick={() => navigate(FB_HOME)}>
          🏠
        </button>

        <input
          style={s.urlInput}
          value={inputUrl}
          onChange={(e) => setInputUrl(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Nhập URL Facebook..."
          spellCheck={false}
        />

        <button style={s.goBtn} onClick={() => navigate(inputUrl)}>
          Đi
        </button>
      </div>

      {hasLoaded ? (
        <div style={s.frameWrap}>
          <iframe
            ref={iframeRef}
            style={s.frame}
            title="Facebook"
            onLoad={handleIframeLoad}
          />
          {overlayVisible && (
            <div style={s.overlay}>
              <span style={{ fontSize: 18 }}>⏳</span> Đang tải...
            </div>
          )}
        </div>
      ) : (
        <div style={s.empty}>
          Chọn tài khoản để mở Facebook
        </div>
      )}
    </div>
  )
}
