const overlay = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999,
}
const panel = {
  background: '#fff', borderRadius: 16, padding: 28, width: 'min(520px, 92vw)',
  maxHeight: '85vh', overflow: 'hidden', display: 'flex', flexDirection: 'column',
  color: '#1c1e21', boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
}
const barBg = { height: 10, background: '#e4e6ea', borderRadius: 5, overflow: 'hidden', margin: '16px 0' }
const barFill = (pct) => ({ height: '100%', width: `${pct}%`, background: '#1877f2', borderRadius: 5, transition: 'width 0.3s' })
const log = { flex: 1, overflowY: 'auto', fontSize: 12, marginTop: 8, borderTop: '1px solid #f0f2f5', paddingTop: 8 }

export default function ProgressOverlay({ visible, title, subtitle, done, total, results = [], current }) {
  if (!visible) return null
  const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0
  const successCount = results.filter((r) => r.success).length

  return (
    <div style={overlay}>
      <div style={panel}>
        <div style={{ fontSize: 20, fontWeight: 700 }}>{title}</div>
        {subtitle && <div style={{ fontSize: 13, color: '#65676b', marginTop: 6 }}>{subtitle}</div>}

        <div style={{ fontSize: 15, fontWeight: 600, marginTop: 16 }}>
          Tiến độ: {done} / {total} ({pct}%)
          {results.length > 0 && (
            <span style={{ color: '#2d7a3a', marginLeft: 8 }}>· ✅ {successCount} thành công</span>
          )}
        </div>
        <div style={barBg}><div style={barFill(pct)} /></div>

        {current && (
          <div style={{ fontSize: 13, color: '#1877f2', marginBottom: 8 }}>
            Đang xử lý: <b>{current.account_email || current.account_id}</b>
            {current.group_name && <> → {current.group_name}</>}
            {current.target_label && <> → {current.target_label}</>}
          </div>
        )}

        <div style={log}>
          {results.length === 0 && (
            <div style={{ color: '#8a8d91' }}>Chờ kết quả đầu tiên...</div>
          )}
          {results.map((r, i) => (
            <div
              key={i}
              style={{
                padding: '6px 0', borderBottom: '1px solid #f7f8fa',
                color: r.success ? '#2d7a3a' : '#d73a3a',
              }}
            >
              {r.success ? '✅' : '❌'}{' '}
              <b>{r.account_email}</b>
              {r.group_name && <> · {r.group_name}</>}
              {r.target_label && <> · {r.target_label}</>}
              {!r.success && r.message && (
                <span style={{ color: '#65676b', display: 'block', marginLeft: 20 }}>{r.message}</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
