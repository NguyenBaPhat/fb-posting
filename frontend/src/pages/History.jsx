import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { getHistory, getSchedules, deleteHistory, deleteSchedule } from '../api'

const s = {
  page: { maxWidth: 900 },
  title: { fontSize: 24, fontWeight: 700, color: '#1877f2', marginBottom: 8 },
  tabs: { display: 'flex', gap: 4, marginBottom: 20, borderBottom: '2px solid #e4e6ea' },
  tab: { padding: '10px 20px', cursor: 'pointer', fontWeight: 600, fontSize: 14, border: 'none', background: 'transparent', borderBottom: '2px solid transparent', marginBottom: -2, color: '#65676b' },
  tabActive: { color: '#1877f2', borderBottom: '2px solid #1877f2' },
  card: { background: '#fff', borderRadius: 12, padding: 20, boxShadow: '0 1px 4px rgba(0,0,0,0.1)', marginBottom: 12 },
  cardHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 },
  content: { fontSize: 14, color: '#1c1e21', lineHeight: 1.5, whiteSpace: 'pre-wrap', background: '#f7f8fa', padding: '10px 14px', borderRadius: 8, marginBottom: 12, maxHeight: 80, overflow: 'hidden' },
  meta: { fontSize: 12, color: '#8a8d91' },
  badge: { display: 'inline-block', padding: '3px 10px', borderRadius: 20, fontWeight: 600, fontSize: 12 },
  badgeSuccess: { background: '#e6f4ea', color: '#2d7a3a' },
  badgeFail: { background: '#ffebe9', color: '#d73a3a' },
  badgePending: { background: '#fff3cd', color: '#856404' },
  badgeRunning: { background: '#e7f3ff', color: '#1877f2' },
  results: { display: 'flex', flexWrap: 'wrap', gap: 8 },
  resultItem: { fontSize: 12, padding: '4px 10px', borderRadius: 8, border: '1px solid #e4e6ea', display: 'flex', alignItems: 'center', gap: 6 },
  btn: { padding: '6px 14px', borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: 12, background: '#ffebe9', color: '#d73a3a' },
  empty: { textAlign: 'center', padding: 60, color: '#65676b' },
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' })
}

function StatusBadge({ status }) {
  const map = { success: s.badgeSuccess, failed: s.badgeFail, pending: s.badgePending, running: s.badgeRunning, done: s.badgeSuccess }
  const label = { success: '✅ Thành công', failed: '❌ Thất bại', pending: '⏳ Đang chờ', running: '🔄 Đang chạy', done: '✅ Hoàn tất' }
  return <span style={{ ...s.badge, ...map[status] }}>{label[status] || status}</span>
}

export default function History() {
  const [tab, setTab] = useState('history')
  const [posts, setPosts] = useState([])
  const [schedules, setSchedules] = useState([])

  const loadHistory = async () => {
    try { const r = await getHistory(); setPosts(r.data) } catch {}
  }
  const loadSchedules = async () => {
    try { const r = await getSchedules(); setSchedules(r.data) } catch {}
  }

  useEffect(() => { loadHistory(); loadSchedules() }, [])

  const delPost = async (id) => {
    if (!confirm('Xóa bản ghi này?')) return
    try { await deleteHistory(id); toast.success('Đã xóa'); loadHistory() } catch {}
  }
  const delSchedule = async (id) => {
    if (!confirm('Hủy lịch đăng này?')) return
    try { await deleteSchedule(id); toast.success('Đã hủy lịch'); loadSchedules() } catch {}
  }

  return (
    <div style={s.page}>
      <h1 style={s.title}>📋 Lịch sử & Lịch hẹn</h1>

      <div style={s.tabs}>
        <button style={{ ...s.tab, ...(tab === 'history' ? s.tabActive : {}) }} onClick={() => setTab('history')}>
          📜 Lịch sử đăng bài ({posts.length})
        </button>
        <button style={{ ...s.tab, ...(tab === 'schedules' ? s.tabActive : {}) }} onClick={() => setTab('schedules')}>
          🕐 Lịch hẹn ({schedules.filter(s => s.status === 'pending').length})
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
              <div>
                <span style={{ fontSize: 12, color: '#8a8d91', marginRight: 10 }}>
                  {formatDate(p.created_at)}
                </span>
                <span style={{ fontSize: 12, background: '#f0f2f5', padding: '2px 8px', borderRadius: 10, color: '#65676b' }}>
                  {p.type === 'scheduled' ? '🕐 Theo lịch' : '🚀 Ngay lập tức'}
                </span>
              </div>
              <button style={s.btn} onClick={() => delPost(p.id)}>Xóa</button>
            </div>

            <div style={s.content}>{p.content}</div>

            <div style={{ marginBottom: 10 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#65676b' }}>
                Kết quả: {p.success_count}/{p.total} nhóm thành công
              </span>
            </div>

            <div style={s.results}>
              {(p.results || []).map((r, i) => (
                <div key={i} style={{ ...s.resultItem, borderColor: r.success ? '#c3e6cb' : '#f5c6cb', background: r.success ? '#f0fff0' : '#fff0f0' }}>
                  <span>{r.success ? '✅' : '❌'}</span>
                  <span><b>{r.group_name}</b> · {r.account_email}</span>
                  {!r.success && <span style={{ color: '#d73a3a' }} title={r.message}>⚠️</span>}
                </div>
              ))}
            </div>
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
              {sc.status === 'pending' && (
                <button style={s.btn} onClick={() => delSchedule(sc.id)}>Hủy lịch</button>
              )}
            </div>
            <div style={s.content}>{sc.content}</div>
            <div style={s.meta}>
              Tạo lúc: {formatDate(sc.created_at)} ·
              {sc.account_ids.length} tài khoản · {sc.group_ids.length} nhóm
            </div>
          </div>
        ))
      )}
    </div>
  )
}
