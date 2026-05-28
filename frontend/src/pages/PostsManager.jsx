import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import {
  getAccounts,
  getGroups,
  getSavedPosts,
  fetchManagedPosts,
  deleteManagedPosts,
  getManagerJob,
} from '../api'
import CheckList from '../components/CheckList'
import ProgressOverlay from '../components/ProgressOverlay'
import { pollJob } from '../utils/pollJob'

/* ── Styles ────────────────────────────────────────────── */
const s = {
  page: { maxWidth: 1080 },
  title: { fontSize: 22, fontWeight: 700, color: '#1877f2', marginBottom: 4 },
  subtitle: { fontSize: 13, color: '#65676b', marginBottom: 20 },

  card: {
    background: '#fff', borderRadius: 12, padding: 20,
    boxShadow: '0 1px 6px rgba(0,0,0,0.08)', marginBottom: 16,
  },
  cardTitle: { fontSize: 14, fontWeight: 700, color: '#1c1e21', marginBottom: 14 },

  // KEY FIX: each child of this grid must be a real div, not a Fragment
  grid2: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 16 },
  panel: {
    background: '#f7f8fa', borderRadius: 10, padding: 14,
    border: '1px solid #e4e6ea',
  },

  row: { display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginTop: 14 },
  radioRow: { display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' },

  btnPrimary: {
    padding: '10px 22px', borderRadius: 8, border: 'none', cursor: 'pointer',
    fontWeight: 700, fontSize: 14, background: '#1877f2', color: '#fff',
    display: 'flex', alignItems: 'center', gap: 6,
  },
  btnDanger: {
    padding: '9px 18px', borderRadius: 8, border: 'none', cursor: 'pointer',
    fontWeight: 700, fontSize: 13, background: '#e41e3f', color: '#fff',
    display: 'flex', alignItems: 'center', gap: 6,
  },
  btnGhost: {
    padding: '7px 14px', borderRadius: 8, border: '1px solid #e4e6ea',
    cursor: 'pointer', fontWeight: 600, fontSize: 12,
    background: '#fff', color: '#65676b',
  },
  disabled: { opacity: 0.5, cursor: 'not-allowed' },

  /* progress */
  progressBox: {
    marginTop: 14, background: '#f0f7ff', borderRadius: 8,
    padding: '12px 14px', border: '1px solid #d0e8ff',
  },
  progressLabel: { fontSize: 13, fontWeight: 600, color: '#1877f2', marginBottom: 6 },
  progressTrack: { height: 8, background: '#d0e8ff', borderRadius: 4, overflow: 'hidden' },
  progressFill: (p) => ({
    height: '100%', width: `${p}%`, background: '#1877f2',
    borderRadius: 4, transition: 'width 0.3s',
  }),
  progressSub: { fontSize: 12, color: '#65676b', marginTop: 6 },

  /* filter bar */
  filterBar: {
    display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center',
    background: '#f7f8fa', borderRadius: 8, padding: '10px 12px', marginBottom: 12,
  },
  select: {
    padding: '6px 10px', borderRadius: 7, border: '1px solid #e4e6ea',
    fontSize: 13, background: '#fff', color: '#1c1e21', minWidth: 150,
  },
  searchInput: {
    flex: 1, minWidth: 160, padding: '6px 12px',
    borderRadius: 7, border: '1px solid #e4e6ea', fontSize: 13,
  },
  clearBtn: {
    padding: '6px 10px', borderRadius: 7, border: 'none',
    background: '#e4e6ea', color: '#65676b', fontSize: 12, cursor: 'pointer', fontWeight: 600,
  },

  /* stats row */
  statsRow: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    marginBottom: 10, gap: 8, flexWrap: 'wrap',
  },
  statsText: { fontSize: 13, color: '#65676b' },
  badge: (color) => ({
    display: 'inline-block', padding: '2px 8px', borderRadius: 10,
    fontSize: 11, fontWeight: 700,
    background: color === 'blue' ? '#e7f3ff' : '#fff3cd',
    color: color === 'blue' ? '#1877f2' : '#856404',
  }),

  /* post item */
  postList: { maxHeight: 540, overflowY: 'auto', paddingRight: 2 },
  postItem: {
    display: 'flex', gap: 10, padding: '11px 6px',
    borderBottom: '1px solid #f0f2f5', alignItems: 'flex-start',
    borderRadius: 6, transition: 'background 0.1s',
  },
  postItemSel: { background: '#f0f7ff' },
  checkBox: { marginTop: 3, cursor: 'pointer', flexShrink: 0, accentColor: '#1877f2' },
  postBody: { flex: 1, minWidth: 0 },
  postMeta: { display: 'flex', gap: 6, alignItems: 'center', marginBottom: 5, flexWrap: 'wrap' },
  groupTag: {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 700,
    background: '#e7f3ff', color: '#1877f2',
  },
  accountTag: {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 600,
    background: '#f0f2f5', color: '#65676b',
  },
  postContent: {
    fontSize: 13, color: '#1c1e21', lineHeight: 1.5, marginBottom: 5,
    display: '-webkit-box', WebkitLineClamp: 2,
    WebkitBoxOrient: 'vertical', overflow: 'hidden',
  },
  postFooter: { display: 'flex', gap: 12, alignItems: 'center' },
  timeText: { fontSize: 11, color: '#8a8d91' },
  viewLink: {
    fontSize: 12, color: '#1877f2', textDecoration: 'none', fontWeight: 600,
  },

  empty: {
    textAlign: 'center', padding: '40px 20px',
    color: '#8a8d91', fontSize: 14,
  },
}

function formatTime(post) {
  if (post.utime) {
    return new Date(post.utime).toLocaleString('vi-VN', {
      dateStyle: 'short', timeStyle: 'short',
    })
  }
  return post.time_text || ''
}

/* ── Component ─────────────────────────────────────────── */
export default function PostsManager() {
  const [accounts, setAccounts] = useState([])
  const [groups, setGroups] = useState([])
  const [selAccounts, setSelAccounts] = useState([])
  const [selGroups, setSelGroups] = useState([])
  const [headless, setHeadless] = useState(true)

  const [fetching, setFetching] = useState(false)
  const [fetchProgress, setFetchProgress] = useState(null)
  const [fetchDone, setFetchDone] = useState(false)
  const [posts, setPosts] = useState([])

  const [deleting, setDeleting] = useState(false)
  const [deleteJob, setDeleteJob] = useState(null)

  const [filterAccount, setFilterAccount] = useState('')
  const [filterGroup, setFilterGroup] = useState('')
  const [searchText, setSearchText] = useState('')
  const [selPosts, setSelPosts] = useState(new Set())

  useEffect(() => {
    Promise.all([getAccounts(), getGroups(), getSavedPosts()])
      .then(([a, g, saved]) => {
        setAccounts(a.data)
        setGroups(g.data)
        if (saved.data?.length) setPosts(saved.data)
      })
      .catch(() => toast.error('Không tải được dữ liệu'))
  }, [])

  /* derived */
  const uniqueAccounts = [
    ...new Map(posts.map(p => [p.account_id, { id: p.account_id, label: p.account_email }])).values(),
  ]
  const uniqueGroups = [
    ...new Map(posts.map(p => [p.group_id, { id: p.group_id, label: p.group_name }])).values(),
  ]

  const filtered = posts.filter(p =>
    (!filterAccount || p.account_id === filterAccount) &&
    (!filterGroup || p.group_id === filterGroup) &&
    (!searchText || (p.content || '').toLowerCase().includes(searchText.toLowerCase()))
  )

  const filteredIds = filtered.map(p => p.id)
  const allFilteredSel = filteredIds.length > 0 && filteredIds.every(id => selPosts.has(id))

  const togglePost = (id) =>
    setSelPosts(prev => {
      const n = new Set(prev)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })

  const toggleAllFiltered = () =>
    setSelPosts(prev => {
      const n = new Set(prev)
      if (allFilteredSel) filteredIds.forEach(id => n.delete(id))
      else filteredIds.forEach(id => n.add(id))
      return n
    })

  /* fetch */
  const handleFetch = async () => {
    if (!selAccounts.length) { toast.error('Chọn ít nhất 1 tài khoản'); return }
    if (!selGroups.length) { toast.error('Chọn ít nhất 1 nhóm'); return }

    setFetching(true)
    setFetchDone(false)
    setSelPosts(new Set())
    setFetchProgress({ done: 0, total: selAccounts.length * selGroups.length, current: null })

    const fd = new FormData()
    fd.append('account_ids', selAccounts.join(','))
    fd.append('group_ids', selGroups.join(','))
    fd.append('headless', headless ? 'true' : 'false')

    try {
      const { data } = await fetchManagedPosts(fd)
      const finished = await pollJob(getManagerJob, data.job_id, (job) => {
        setFetchProgress({ done: job.done, total: job.total, current: job.current })
      })
      const result = finished.record?.posts ?? []
      setPosts(result)
      setFetchDone(true)
      if (result.length > 0) toast.success(`Tìm thấy ${result.length} bài viết`)
      else toast('Không tìm thấy bài nào trong các nhóm đã quét', { icon: '📭' })
    } catch (err) {
      toast.error(err.message || 'Lỗi khi quét bài viết')
    } finally {
      setFetching(false)
      setFetchProgress(null)
    }
  }

  /* delete */
  const handleDelete = async () => {
    const toDelete = posts.filter(p => selPosts.has(p.id))
    if (!toDelete.length) { toast.error('Chưa chọn bài nào'); return }
    if (!confirm(`Xóa ${toDelete.length} bài viết?\nHành động này KHÔNG THỂ hoàn tác!`)) return

    setDeleting(true)
    setDeleteJob({ done: 0, total: toDelete.length, results: [], current: null })

    const fd = new FormData()
    fd.append('items', JSON.stringify(toDelete.map(p => ({
      account_id: p.account_id,
      account_email: p.account_email,
      post_url: p.post_url,
      group_name: p.group_name,
    }))))
    fd.append('headless', headless ? 'true' : 'false')

    try {
      const { data } = await deleteManagedPosts(fd)
      const finished = await pollJob(getManagerJob, data.job_id, (job) => {
        setDeleteJob({ done: job.done, total: job.total, results: job.results, current: job.current })
      })
      const { success_count = 0, total: t = 0, results = [] } = finished.record || {}

      const deletedUrls = new Set(results.filter(r => r.success).map(r => r.post_url))
      setPosts(prev => prev.filter(p => !deletedUrls.has(p.post_url)))
      setSelPosts(new Set())

      if (success_count === t) toast.success(`✅ Đã xóa ${success_count}/${t} bài`)
      else if (success_count > 0) toast(`⚠️ Xóa ${success_count}/${t} — một số thất bại`)
      else toast.error('❌ Không xóa được bài nào')
    } catch (err) {
      toast.error(err.message || 'Lỗi xóa bài viết')
    } finally {
      setDeleting(false)
      setDeleteJob(null)
    }
  }

  const fetchPct = fetchProgress && fetchProgress.total > 0
    ? Math.round((fetchProgress.done / fetchProgress.total) * 100)
    : 0

  /* ── Render ──────────────────────────────────────────── */
  return (
    <div style={s.page}>
      <ProgressOverlay
        visible={deleting && !!deleteJob}
        title="Đang xóa bài viết..."
        subtitle={headless ? 'Chạy ngầm...' : 'Chrome đang mở'}
        done={deleteJob?.done ?? 0}
        total={deleteJob?.total ?? 0}
        results={deleteJob?.results ?? []}
        current={deleteJob?.current}
      />

      <h1 style={s.title}>🗂️ Quản lý bài đăng</h1>
      <p style={s.subtitle}>
        Quét bài đăng trực tiếp từ Facebook theo từng tài khoản (kể cả bài đăng tay), lọc và xóa hàng loạt.
      </p>

      {/* ── Bước 1: Chọn & quét ── */}
      <div style={s.card}>
        <div style={s.cardTitle}>📋 Chọn tài khoản & nhóm cần quét</div>

        {/* Wrap each CheckList in a real div to fix CSS Grid Fragment bug */}
        <div style={s.grid2}>
          <div style={s.panel}>
            <CheckList
              title="Tài khoản"
              icon="👤"
              items={accounts}
              selected={selAccounts}
              onToggle={(id) =>
                setSelAccounts(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id])
              }
              onSelectAll={setSelAccounts}
              emptyText={<>Chưa có tài khoản. <a href="/accounts">Thêm tại đây</a></>}
              renderItem={(acc) => (
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{acc.name || acc.email}</div>
                  <div style={{ fontSize: 12, color: '#8a8d91' }}>{acc.email}</div>
                </div>
              )}
            />
          </div>

          <div style={s.panel}>
            <CheckList
              title="Nhóm cần quét"
              icon="👥"
              items={groups}
              selected={selGroups}
              onToggle={(id) =>
                setSelGroups(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id])
              }
              onSelectAll={setSelGroups}
              emptyText={<>Chưa có nhóm. <a href="/groups">Thêm tại đây</a></>}
              renderItem={(g) => (
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{g.name}</div>
                  <div style={{ fontSize: 11, color: '#8a8d91', wordBreak: 'break-all' }}>{g.url}</div>
                </div>
              )}
            />
          </div>
        </div>

        {/* Browser mode + fetch button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
          <label style={s.radioRow}>
            <input type="radio" checked={headless} onChange={() => setHeadless(true)} />
            Chạy ngầm
          </label>
          <label style={s.radioRow}>
            <input type="radio" checked={!headless} onChange={() => setHeadless(false)} />
            Hiện trình duyệt (xử lý 2FA)
          </label>

          <button
            style={{ ...s.btnPrimary, ...(fetching ? s.disabled : {}), marginLeft: 'auto' }}
            disabled={fetching}
            onClick={handleFetch}
          >
            {fetching ? (
              <>⏳ Đang quét...</>
            ) : (
              <>🔍 Tải bài đăng từ Facebook</>
            )}
          </button>
        </div>

        {/* Fetch progress bar */}
        {fetching && fetchProgress && (
          <div style={s.progressBox}>
            <div style={s.progressLabel}>
              Đang quét {fetchProgress.done} / {fetchProgress.total} nhóm ({fetchPct}%)
            </div>
            <div style={s.progressTrack}>
              <div style={s.progressFill(fetchPct)} />
            </div>
            {fetchProgress.current && (
              <div style={s.progressSub}>
                {fetchProgress.current.account_email && (
                  <b>{fetchProgress.current.account_email}</b>
                )}
                {fetchProgress.current.label && (
                  <> — {fetchProgress.current.label}</>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Bước 2: Kết quả ── */}
      {fetchDone && (
        <div style={s.card}>
          <div style={{ ...s.cardTitle, marginBottom: 10 }}>
            📌 Kết quả quét
            {posts.length > 0 && (
              <span style={{ ...s.badge('blue'), marginLeft: 8 }}>
                {posts.length} bài
              </span>
            )}
          </div>

          {posts.length === 0 ? (
            <div style={s.empty}>
              <div style={{ fontSize: 40, marginBottom: 8 }}>📭</div>
              <div>Không tìm thấy bài viết nào trong các nhóm đã quét.</div>
              <div style={{ fontSize: 12, marginTop: 6 }}>
                Thử chọn thêm nhóm hoặc kiểm tra tài khoản đã đăng bài trong nhóm chưa.
              </div>
            </div>
          ) : (
            <>
              {/* Filter bar */}
              <div style={s.filterBar}>
                <select
                  style={s.select}
                  value={filterAccount}
                  onChange={e => { setFilterAccount(e.target.value); setSelPosts(new Set()) }}
                >
                  <option value="">Tất cả tài khoản</option>
                  {uniqueAccounts.map(a => (
                    <option key={a.id} value={a.id}>{a.label}</option>
                  ))}
                </select>

                <select
                  style={s.select}
                  value={filterGroup}
                  onChange={e => { setFilterGroup(e.target.value); setSelPosts(new Set()) }}
                >
                  <option value="">Tất cả nhóm</option>
                  {uniqueGroups.map(g => (
                    <option key={g.id} value={g.id}>{g.label}</option>
                  ))}
                </select>

                <input
                  style={s.searchInput}
                  placeholder="🔎 Tìm theo nội dung..."
                  value={searchText}
                  onChange={e => setSearchText(e.target.value)}
                />

                {(filterAccount || filterGroup || searchText) && (
                  <button
                    style={s.clearBtn}
                    onClick={() => { setFilterAccount(''); setFilterGroup(''); setSearchText('') }}
                  >
                    ✕ Xóa lọc
                  </button>
                )}
              </div>

              {/* Stats + actions */}
              <div style={s.statsRow}>
                <div style={s.statsText}>
                  Hiển thị <b>{filtered.length}</b>/{posts.length} bài
                  {selPosts.size > 0 && (
                    <span style={{ color: '#1877f2', marginLeft: 8, fontWeight: 600 }}>
                      · Đã chọn {selPosts.size}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  {filtered.length > 0 && (
                    <button style={s.btnGhost} onClick={toggleAllFiltered}>
                      {allFilteredSel ? 'Bỏ chọn tất cả' : `Chọn ${filtered.length} bài`}
                    </button>
                  )}
                  {selPosts.size > 0 && (
                    <button
                      style={{ ...s.btnDanger, ...(deleting ? s.disabled : {}) }}
                      disabled={deleting}
                      onClick={handleDelete}
                    >
                      🗑️ Xóa {selPosts.size} bài đã chọn
                    </button>
                  )}
                </div>
              </div>

              {/* Post list */}
              {filtered.length === 0 ? (
                <div style={s.empty}>Không có bài nào khớp bộ lọc</div>
              ) : (
                <div style={s.postList}>
                  {filtered.map(post => {
                    const selected = selPosts.has(post.id)
                    return (
                      <div
                        key={post.id}
                        style={{ ...s.postItem, ...(selected ? s.postItemSel : {}) }}
                        onClick={() => togglePost(post.id)}
                      >
                        <input
                          type="checkbox"
                          style={s.checkBox}
                          checked={selected}
                          onChange={() => togglePost(post.id)}
                          onClick={e => e.stopPropagation()}
                        />
                        <div style={s.postBody}>
                          <div style={s.postMeta}>
                            <span style={s.groupTag}>👥 {post.group_name}</span>
                            <span style={s.accountTag}>👤 {post.account_email}</span>
                          </div>

                          {post.content ? (
                            <div style={s.postContent}>{post.content}</div>
                          ) : (
                            <div style={{ ...s.postContent, color: '#8a8d91', fontStyle: 'italic' }}>
                              (bài không có nội dung văn bản)
                            </div>
                          )}

                          <div style={s.postFooter}>
                            {formatTime(post) && (
                              <span style={s.timeText}>🕐 {formatTime(post)}</span>
                            )}
                            {post.post_url && (
                              <a
                                href={post.post_url}
                                target="_blank"
                                rel="noreferrer"
                                style={s.viewLink}
                                onClick={e => e.stopPropagation()}
                              >
                                Xem bài →
                              </a>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
