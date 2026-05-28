import { useEffect, useState } from 'react'
import { getHistory, getSchedules, getAccounts } from '../api'

const s = {
  page: { maxWidth: 960 },
  title: { fontSize: 24, fontWeight: 700, color: '#1877f2', marginBottom: 8 },
  tabs: { display: 'flex', gap: 4, marginBottom: 20, borderBottom: '2px solid #e4e6ea' },
  tab: {
    padding: '10px 20px', cursor: 'pointer', fontWeight: 600, fontSize: 14,
    border: 'none', background: 'transparent', borderBottom: '2px solid transparent',
    marginBottom: -2, color: '#65676b',
  },
  tabActive: { color: '#1877f2', borderBottom: '2px solid #1877f2' },
  card: {
    background: '#fff', borderRadius: 12, padding: 20,
    boxShadow: '0 1px 4px rgba(0,0,0,0.1)', marginBottom: 12,
  },
  cardHeader: {
    display: 'flex', justifyContent: 'space-between',
    alignItems: 'flex-start', marginBottom: 12,
  },
  content: {
    fontSize: 14, color: '#1c1e21', lineHeight: 1.6,
    whiteSpace: 'pre-wrap', background: '#f7f8fa',
    padding: '10px 14px', borderRadius: 8, marginBottom: 14,
    maxHeight: 160, overflowY: 'auto',
  },
  meta: { fontSize: 12, color: '#8a8d91' },
  badge: { display: 'inline-block', padding: '3px 10px', borderRadius: 20, fontWeight: 600, fontSize: 12 },
  badgeSuccess: { background: '#e6f4ea', color: '#2d7a3a' },
  badgeFail: { background: '#ffebe9', color: '#d73a3a' },
  badgePending: { background: '#fff3cd', color: '#856404' },
  badgeRunning: { background: '#e7f3ff', color: '#1877f2' },
  btn: {
    padding: '6px 14px', borderRadius: 8, border: 'none',
    cursor: 'pointer', fontWeight: 600, fontSize: 12,
    background: '#ffebe9', color: '#d73a3a',
  },
  empty: { textAlign: 'center', padding: 60, color: '#65676b' },
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' })
}

function StatusBadge({ status }) {
  const styles = {
    success: s.badgeSuccess, failed: s.badgeFail, pending: s.badgePending,
    running: s.badgeRunning, done: s.badgeSuccess, active: s.badgeRunning,
  }
  const labels = {
    success: '✅ Thành công', failed: '❌ Thất bại', pending: '⏳ Đang chờ',
    running: '🔄 Đang chạy', done: '✅ Hoàn tất', active: '🔁 Đang lặp',
  }
  return <span style={{ ...s.badge, ...styles[status] }}>{labels[status] || status}</span>
}

function recurrenceText(sc) {
  if (!sc.recurrence || sc.recurrence === 'once') return null
  const n = sc.recurrence_interval || 1
  const map = {
    hourly: `Mỗi ${n} giờ`, daily: 'Hằng ngày',
    weekly: 'Hằng tuần', every_n_days: `Mỗi ${n} ngày`,
  }
  return map[sc.recurrence] || sc.recurrence_label
}

// Gom kết quả theo account, trả về [{accountLabel, successes, failures}]
function groupByAccount(results, accountMap) {
  const map = {}
  for (const r of results || []) {
    const key = r.account_id || r.account_email || '?'
    if (!map[key]) {
      const name = accountMap[key] || accountMap[r.account_email] || r.account_email || key
      map[key] = { label: name, successes: [], failures: [] }
    }
    if (r.success) {
      map[key].successes.push(r.group_name || r.group_url || '?')
    } else {
      const msg = r.message ? `: ${r.message}` : ''
      map[key].failures.push(`${r.group_name || '?'}${msg}`)
    }
  }
  return Object.values(map)
}

function ResultRow({ results, accountMap }) {
  const groups = groupByAccount(results, accountMap)
  if (!groups.length) return null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {groups.map((g, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#1c1e21', minWidth: 90 }}>
            👤 {g.label}
          </span>
          {g.successes.length > 0 && (
            <span
              title={g.successes.join('\n')}
              style={{
                padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                background: '#e6f4ea', color: '#2d7a3a', border: '1px solid #c3e6cb',
                cursor: 'default',
              }}
            >
              ✅ {g.successes.length} nhóm
            </span>
          )}
          {g.failures.length > 0 && (
            <span
              title={g.failures.join('\n')}
              style={{
                padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                background: '#ffebe9', color: '#d73a3a', border: '1px solid #f5c6cb',
                cursor: 'default',
              }}
            >
              ❌ {g.failures.length} nhóm
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

export default function History() {
  const [tab, setTab] = useState('history')
  const [posts, setPosts] = useState([])
  const [schedules, setSchedules] = useState([])
  const [accountMap, setAccountMap] = useState({})

  const loadHistory = async () => {
    try { const r = await getHistory(); setPosts(r.data) } catch {}
  }
  const loadSchedules = async () => {
    try { const r = await getSchedules(); setSchedules(r.data) } catch {}
  }
  const loadAccounts = async () => {
    try {
      const r = await getAccounts()
      const map = {}
      for (const a of r.data || []) {
        map[a.id] = a.name || a.email
        map[a.email] = a.name || a.email
      }
      setAccountMap(map)
    } catch {}
  }

  useEffect(() => { loadHistory(); loadSchedules(); loadAccounts() }, [])

  return (
    <div style={s.page}>
      <h1 style={s.title}>📋 Lịch sử & Lịch hẹn</h1>

      <div style={s.tabs}>
        <button
          style={{ ...s.tab, ...(tab === 'history' ? s.tabActive : {}) }}
          onClick={() => setTab('history')}
        >
          📜 Lịch sử đăng bài ({posts.length})
        </button>
        <button
          style={{ ...s.tab, ...(tab === 'schedules' ? s.tabActive : {}) }}
          onClick={() => setTab('schedules')}
        >
          🕐 Lịch hẹn ({schedules.filter(sc => ['pending', 'active'].includes(sc.status)).length})
        </button>
      </div>

      {tab === 'history' && (
        posts.length === 0 ? (
          <div style={s.empty}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>📭</div>
            <div style={{ fontSize: 16, fontWeight: 600 }}>Chưa có bài đăng nào</div>
          </div>
        ) : posts.map(p => (
          <div key={p.id} style={s.card}>
            <div style={s.cardHeader}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 12, color: '#8a8d91' }}>{formatDate(p.created_at)}</span>
                <span style={{
                  fontSize: 12, background: '#f0f2f5',
                  padding: '2px 8px', borderRadius: 10, color: '#65676b',
                }}>
                  {p.type === 'scheduled' ? '🕐 Theo lịch' : '🚀 Ngay lập tức'}
                </span>
                {p.status === 'running' && (
                  <span style={{ ...s.badge, ...s.badgeRunning }}>🔄 Đang đăng...</span>
                )}
                <span style={{ fontSize: 12, color: '#65676b', fontWeight: 600 }}>
                  {p.success_count}/{p.total} nhóm thành công
                </span>
              </div>
            </div>

            <div style={s.content}>{p.content || <em style={{ color: '#aaa' }}>Không có nội dung</em>}</div>

            <ResultRow results={p.results} accountMap={accountMap} />
          </div>
        ))
      )}

      {tab === 'schedules' && (
        schedules.length === 0 ? (
          <div style={s.empty}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>🗓️</div>
            <div style={{ fontSize: 16, fontWeight: 600 }}>Chưa có lịch hẹn nào</div>
          </div>
        ) : schedules.map(sc => (
          <div key={sc.id} style={s.card}>
            <div style={s.cardHeader}>
              <div>
                <StatusBadge status={sc.status} />
                <span style={{ fontSize: 12, color: '#8a8d91', marginLeft: 10 }}>
                  Đăng lúc: <b>{formatDate(sc.scheduled_at)}</b>
                </span>
              </div>
            </div>
            <div style={s.content}>{sc.content}</div>
            {recurrenceText(sc) && (
              <div style={{ fontSize: 12, color: '#1877f2', marginBottom: 8 }}>
                🔁 {recurrenceText(sc)}
              </div>
            )}
            <div style={s.meta}>
              Tạo lúc: {formatDate(sc.created_at)} ·
              {sc.account_ids.length} tài khoản · {sc.group_ids.length} nhóm
              {sc.run_count > 0 && <> · Đã chạy {sc.run_count} lần</>}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
