import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { getAccounts, getCommentTargets, sendComments, getCommentJob } from '../api'
import CheckList from '../components/CheckList'
import ProgressOverlay from '../components/ProgressOverlay'
import { pollJob } from '../utils/pollJob'

const s = {
  page: { maxWidth: 960 },
  title: { fontSize: 24, fontWeight: 700, color: '#1877f2', marginBottom: 8 },
  subtitle: { fontSize: 14, color: '#65676b', marginBottom: 24 },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 },
  section: { background: '#fff', borderRadius: 12, padding: 20, boxShadow: '0 1px 4px rgba(0,0,0,0.1)', marginBottom: 20 },
  sectionHead: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  scrollBox: { maxHeight: 320, overflowY: 'auto', paddingRight: 4 },
  selectAll: { fontSize: 12, color: '#1877f2', cursor: 'pointer', fontWeight: 600, border: 'none', background: 'none' },
  targetItem: { padding: '10px 0', borderBottom: '1px solid #f0f2f5' },
  targetMeta: { fontSize: 12, color: '#65676b', marginTop: 4 },
  urlInput: { width: '100%', marginTop: 6, padding: '6px 10px', borderRadius: 6, border: '1px solid #e4e6ea', fontSize: 12 },
  textarea: { width: '100%', minHeight: 100, padding: '12px 14px', borderRadius: 8, border: '1.5px solid #e4e6ea', fontSize: 15, resize: 'vertical', outline: 'none', fontFamily: 'inherit' },
  btn: { padding: '10px 24px', borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 700, fontSize: 14, background: '#1877f2', color: '#fff' },
  btnSecondary: { background: '#e7f3ff', color: '#1877f2', fontSize: 13, padding: '8px 14px', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600 },
  btnDisabled: { opacity: 0.5, cursor: 'not-allowed' },
  badge: { fontSize: 11, padding: '2px 8px', borderRadius: 10, background: '#fff3cd', color: '#856404' },
  badgeOk: { background: '#e6f4ea', color: '#2d7a3a' },
  empty: { textAlign: 'center', padding: 24, color: '#65676b', fontSize: 14 },
  browserOption: { display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 8, cursor: 'pointer', fontSize: 13 },
}

export default function Comments() {
  const [accounts, setAccounts] = useState([])
  const [targets, setTargets] = useState([])
  const [selAccounts, setSelAccounts] = useState([])
  const [selTargets, setSelTargets] = useState([])
  const [urlOverrides, setUrlOverrides] = useState({})
  const [manualTargets, setManualTargets] = useState([])
  const [headless, setHeadless] = useState(true)
  const [sending, setSending] = useState(false)
  const [job, setJob] = useState(null)
  const commentRef = useRef()

  const allTargetItems = [
    ...targets.map(t => ({ ...t, _type: 'history' })),
    ...manualTargets.map(t => ({ ...t, _type: 'manual' })),
  ]

  const load = async () => {
    try {
      const [acc, tgt] = await Promise.all([getAccounts(), getCommentTargets()])
      setAccounts(acc.data)
      setTargets(tgt.data)
    } catch {
      toast.error('Không tải được dữ liệu')
    }
  }

  useEffect(() => { load() }, [])

  const toggleTarget = (id) => setSelTargets(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id])
  const targetIds = allTargetItems.map(t => t.id)
  const allTargetsSelected = targetIds.length > 0 && targetIds.every(id => selTargets.includes(id))

  const toggleAllTargets = () => {
    if (allTargetsSelected) setSelTargets([])
    else setSelTargets([...targetIds])
  }

  const addManualTarget = () => {
    const id = `manual-${Date.now()}`
    setManualTargets(p => [...p, { id, post_url: '', label: 'Link thủ công' }])
    setSelTargets(p => [...p, id])
  }

  const buildTargetPayload = () => {
    const fromHistory = targets
      .filter(t => selTargets.includes(t.id))
      .map(t => ({
        id: t.id,
        post_url: (urlOverrides[t.id] ?? t.post_url ?? '').trim(),
        group_url: t.group_url,
        group_name: t.group_name,
        post_content: t.post_content,
        label: `${t.group_name} · ${t.account_email}`,
      }))
    const fromManual = manualTargets
      .filter(t => selTargets.includes(t.id))
      .map(t => ({
        id: t.id,
        post_url: (t.post_url || '').trim(),
        label: t.label || 'Link thủ công',
      }))
    return [...fromHistory, ...fromManual]
  }

  const totalTasks = selAccounts.length * buildTargetPayload().length

  const handleSend = async () => {
    const content = (commentRef.current?.value ?? '').trim()
    if (!content) { toast.error('Nhập nội dung bình luận'); return }
    if (selAccounts.length === 0) { toast.error('Chọn ít nhất 1 tài khoản'); return }
    const payload = buildTargetPayload()
    if (payload.length === 0) { toast.error('Chọn ít nhất 1 bài viết'); return }
    if (payload.some(t => !t.post_url && !t.group_url)) {
      toast.error('Một số bài chưa có link — dán URL bài viết Facebook')
      return
    }

    setSending(true)
    setJob({ status: 'running', done: 0, total: selAccounts.length * payload.length, results: [] })
    try {
      const fd = new FormData()
      fd.append('content', content)
      fd.append('account_ids', selAccounts.join(','))
      fd.append('targets', JSON.stringify(payload))
      fd.append('headless', headless ? 'true' : 'false')
      const start = await sendComments(fd)
      const { job_id, total } = start.data
      const finished = await pollJob(getCommentJob, job_id, setJob)
      const record = finished.record || {}
      const { success_count = 0, total: t = 0 } = record
      if (success_count === t) toast.success(`✅ Bình luận thành công ${success_count}/${t}`)
      else if (success_count > 0) toast.success(`⚠️ Thành công ${success_count}/${t}`)
      else toast.error(`❌ Thất bại cả ${t} lần`)
      if (commentRef.current) commentRef.current.value = ''
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || 'Lỗi gửi bình luận')
    } finally {
      setSending(false)
      setJob(null)
    }
  }

  return (
    <div style={s.page}>
      <ProgressOverlay
        visible={sending && job}
        title="Đang gửi bình luận..."
        subtitle={headless ? 'Đang tự động bình luận...' : 'Chrome đang mở — xử lý 2FA nếu cần'}
        done={job?.done ?? 0}
        total={job?.total ?? totalTasks}
        results={job?.results ?? []}
        current={job?.current}
      />

      <h1 style={s.title}>💬 Bình luận bài viết</h1>
      <p style={s.subtitle}>
        Chọn bài, chọn tài khoản bình luận (có thể khác TK đăng bài), nhập nội dung tùy chỉnh.
      </p>

      <div style={s.grid}>
        <div style={s.section}>
          <CheckList
            title="Tài khoản bình luận"
            icon="👤"
            items={accounts}
            selected={selAccounts}
            onToggle={(id) => setSelAccounts(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id])}
            onSelectAll={setSelAccounts}
            emptyText={<>Chưa có tài khoản. <a href="/accounts">Thêm tài khoản</a></>}
            renderItem={(acc) => (
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{acc.name}</div>
                <div style={s.targetMeta}>{acc.email}</div>
              </div>
            )}
          />
        </div>

        <div style={s.section}>
          <div style={s.sectionHead}>
            <div style={{ fontSize: 14, fontWeight: 700 }}>📌 Bài viết mục tiêu</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {targetIds.length > 0 && (
                <button type="button" style={s.selectAll} onClick={toggleAllTargets}>
                  {allTargetsSelected ? 'Bỏ chọn tất cả' : 'Chọn tất cả'}
                </button>
              )}
              <button type="button" style={s.btnSecondary} onClick={addManualTarget}>+ Link</button>
            </div>
          </div>

          {allTargetItems.length === 0 ? (
            <div style={s.empty}>Chưa có bài trong lịch sử. Dùng「+ Link」để dán URL.</div>
          ) : (
            <div style={s.scrollBox}>
              {targets.map(t => (
                <div key={t.id} style={s.targetItem}>
                  <label style={{ display: 'flex', gap: 8, cursor: 'pointer' }}>
                    <input type="checkbox" checked={selTargets.includes(t.id)} onChange={() => toggleTarget(t.id)} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>{t.group_name}</div>
                      <div style={s.targetMeta}>Đăng bởi: {t.account_email}</div>
                      <div style={{ ...s.targetMeta, marginTop: 4 }}>{t.post_content}</div>
                      <span style={{ ...s.badge, ...(t.post_url ? s.badgeOk : {}), marginTop: 6, display: 'inline-block' }}>
                        {t.post_url ? '✓ Có link' : '⚠ Cần dán link'}
                      </span>
                      <input
                        style={s.urlInput}
                        placeholder="URL bài viết Facebook"
                        value={urlOverrides[t.id] ?? t.post_url ?? ''}
                        onChange={e => setUrlOverrides(p => ({ ...p, [t.id]: e.target.value }))}
                      />
                    </div>
                  </label>
                </div>
              ))}
              {manualTargets.map(t => (
                <div key={t.id} style={s.targetItem}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input type="checkbox" checked={selTargets.includes(t.id)} onChange={() => toggleTarget(t.id)} />
                    <input
                      style={{ ...s.urlInput, flex: 1, marginTop: 0 }}
                      placeholder="Nhãn"
                      value={t.label}
                      onChange={e => setManualTargets(p => p.map(x => x.id === t.id ? { ...x, label: e.target.value } : x))}
                    />
                    <button
                      type="button"
                      style={{ ...s.btnSecondary, background: '#ffebe9', color: '#d73a3a' }}
                      onClick={() => {
                        setManualTargets(p => p.filter(x => x.id !== t.id))
                        setSelTargets(p => p.filter(x => x !== t.id))
                      }}
                    >✕</button>
                  </div>
                  <input
                    style={{ ...s.urlInput, marginLeft: 28 }}
                    placeholder="URL bài viết *"
                    value={t.post_url}
                    onChange={e => setManualTargets(p => p.map(x => x.id === t.id ? { ...x, post_url: e.target.value } : x))}
                  />
                </div>
              ))}
            </div>
          )}
          <div style={{ fontSize: 12, color: '#65676b', marginTop: 8 }}>
            {selTargets.length} / {targetIds.length} bài · {totalTasks} lượt bình luận
          </div>
        </div>
      </div>

      <div style={s.section}>
        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 14 }}>✏️ Nội dung bình luận</div>
        <textarea ref={commentRef} style={s.textarea} placeholder="Nhập nội dung bình luận..." />
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>🌐 Chế độ trình duyệt</div>
          <label style={s.browserOption}>
            <input type="radio" checked={headless} onChange={() => setHeadless(true)} /> Chạy ngầm
          </label>
          <label style={s.browserOption}>
            <input type="radio" checked={!headless} onChange={() => setHeadless(false)} /> Hiện trình duyệt
          </label>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
          <button type="button" style={{ ...s.btn, ...(sending ? s.btnDisabled : {}) }} disabled={sending} onClick={handleSend}>
            {sending ? '⏳ Đang gửi...' : '💬 Gửi bình luận'}
          </button>
        </div>
      </div>
    </div>
  )
}
