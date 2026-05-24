import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { getAccounts, getGroups, sendPost, createSchedule } from '../api'

const s = {
  page: { maxWidth: 900 },
  title: { fontSize: 24, fontWeight: 700, color: '#1877f2', marginBottom: 24 },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 },
  section: { background: '#fff', borderRadius: 12, padding: 20, boxShadow: '0 1px 4px rgba(0,0,0,0.1)' },
  sectionTitle: { fontSize: 14, fontWeight: 700, marginBottom: 14, color: '#1c1e21', display: 'flex', alignItems: 'center', gap: 8 },
  checkItem: { display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid #f0f2f5', cursor: 'pointer' },
  checkLabel: { fontSize: 14, cursor: 'pointer' },
  checkSub: { fontSize: 12, color: '#65676b' },
  composer: { background: '#fff', borderRadius: 12, padding: 20, boxShadow: '0 1px 4px rgba(0,0,0,0.1)', marginBottom: 20 },
  textarea: { width: '100%', minHeight: 140, padding: '12px 14px', borderRadius: 8, border: '1.5px solid #e4e6ea', fontSize: 15, resize: 'vertical', outline: 'none', fontFamily: 'inherit', lineHeight: 1.5 },
  imagePreview: { marginTop: 12, position: 'relative', display: 'inline-block' },
  imgThumb: { maxHeight: 120, borderRadius: 8, border: '2px solid #e4e6ea' },
  removeImg: { position: 'absolute', top: -8, right: -8, background: '#d73a3a', color: '#fff', border: 'none', borderRadius: '50%', width: 22, height: 22, cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center' },
  toolRow: { display: 'flex', gap: 10, marginTop: 12, alignItems: 'center', flexWrap: 'wrap' },
  uploadBtn: { display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 8, border: '1.5px dashed #1877f2', background: '#e7f3ff', color: '#1877f2', cursor: 'pointer', fontSize: 13, fontWeight: 600 },
  scheduleRow: { display: 'flex', alignItems: 'center', gap: 10, padding: '12px 0', borderTop: '1px solid #f0f2f5', marginTop: 12 },
  scheduleInput: { padding: '8px 12px', borderRadius: 8, border: '1.5px solid #e4e6ea', fontSize: 13, outline: 'none' },
  actionRow: { display: 'flex', gap: 12, justifyContent: 'flex-end' },
  btn: { padding: '10px 24px', borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 700, fontSize: 14 },
  btnPost: { background: '#1877f2', color: '#fff', minWidth: 140 },
  btnSchedule: { background: '#e7f3ff', color: '#1877f2', minWidth: 140 },
  btnDisabled: { opacity: 0.5, cursor: 'not-allowed' },
  selCount: { fontSize: 12, color: '#65676b', marginTop: 8 },
  progressOverlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', zIndex: 9999,
    color: '#fff',
  },
  spinner: { fontSize: 48, marginBottom: 16, animation: 'spin 1.2s linear infinite' },
}

export default function Composer() {
  const [accounts, setAccounts] = useState([])
  const [groups, setGroups] = useState([])
  const [selAccounts, setSelAccounts] = useState([])
  const [selGroups, setSelGroups] = useState([])
  const [content, setContent] = useState('')
  const [image, setImage] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [scheduleAt, setScheduleAt] = useState('')
  const [useSchedule, setUseSchedule] = useState(false)
  const [posting, setPosting] = useState(false)
  const fileRef = useRef()

  useEffect(() => {
    getAccounts().then(r => setAccounts(r.data)).catch(() => {})
    getGroups().then(r => setGroups(r.data)).catch(() => {})
  }, [])

  const toggleAcc = (id) => setSelAccounts(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id])
  const toggleGroup = (id) => setSelGroups(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id])

  const onImage = (e) => {
    const file = e.target.files[0]
    if (!file) return
    setImage(file)
    setImagePreview(URL.createObjectURL(file))
  }

  const removeImage = () => { setImage(null); setImagePreview(null); fileRef.current.value = '' }

  const canPost = content.trim() && selAccounts.length > 0 && selGroups.length > 0

  const handlePost = async () => {
    if (!canPost) { toast.error('Chọn ít nhất 1 tài khoản, 1 nhóm và nhập nội dung'); return }
    setPosting(true)
    try {
      const fd = new FormData()
      fd.append('content', content)
      fd.append('account_ids', selAccounts.join(','))
      fd.append('group_ids', selGroups.join(','))
      if (image) fd.append('image', image)
      const res = await sendPost(fd)
      const { success_count, total } = res.data
      if (success_count === total) toast.success(`✅ Đăng bài thành công ${success_count}/${total} nhóm!`)
      else if (success_count > 0) toast.success(`⚠️ Thành công ${success_count}/${total} nhóm`)
      else toast.error(`❌ Đăng bài thất bại cả ${total} nhóm`)
      setContent('')
      removeImage()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Lỗi đăng bài')
    } finally { setPosting(false) }
  }

  const handleSchedule = async () => {
    if (!canPost) { toast.error('Chọn ít nhất 1 tài khoản, 1 nhóm và nhập nội dung'); return }
    if (!scheduleAt) { toast.error('Vui lòng chọn thời gian đăng bài'); return }
    try {
      await createSchedule({
        content,
        account_ids: selAccounts,
        group_ids: selGroups,
        scheduled_at: new Date(scheduleAt).toISOString().slice(0, 19),
        image_path: null,
      })
      toast.success('✅ Đã lên lịch đăng bài!')
      setContent('')
      setUseSchedule(false)
      setScheduleAt('')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Lỗi khi lên lịch')
    }
  }

  return (
    <div style={s.page}>
      {posting && (
        <div style={s.progressOverlay}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>⏳</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>Đang đăng bài...</div>
          <div style={{ fontSize: 14, marginTop: 8, opacity: 0.8 }}>
            Trình duyệt đang mở, vui lòng không đóng cửa sổ
          </div>
        </div>
      )}

      <h1 style={s.title}>✍️ Soạn & Đăng bài</h1>

      {/* Account & Group selectors */}
      <div style={s.grid}>
        <div style={s.section}>
          <div style={s.sectionTitle}><span>👤</span> Tài khoản đăng bài</div>
          {accounts.length === 0 ? (
            <div style={{ color: '#65676b', fontSize: 13 }}>Chưa có tài khoản. <a href="/accounts" style={{ color: '#1877f2' }}>Thêm ngay</a></div>
          ) : accounts.map(acc => (
            <label key={acc.id} style={s.checkItem}>
              <input type="checkbox" checked={selAccounts.includes(acc.id)} onChange={() => toggleAcc(acc.id)} />
              <div>
                <div style={s.checkLabel}>{acc.name}</div>
                <div style={s.checkSub}>{acc.email}</div>
              </div>
            </label>
          ))}
          <div style={s.selCount}>{selAccounts.length} tài khoản được chọn</div>
        </div>

        <div style={s.section}>
          <div style={s.sectionTitle}><span>👥</span> Nhóm đăng bài</div>
          {groups.length === 0 ? (
            <div style={{ color: '#65676b', fontSize: 13 }}>Chưa có nhóm. <a href="/groups" style={{ color: '#1877f2' }}>Thêm ngay</a></div>
          ) : groups.map(g => (
            <label key={g.id} style={s.checkItem}>
              <input type="checkbox" checked={selGroups.includes(g.id)} onChange={() => toggleGroup(g.id)} />
              <div>
                <div style={s.checkLabel}>{g.name}</div>
                <div style={s.checkSub} title={g.url}>{g.url.replace('https://www.facebook.com/groups/', 'groups/')}</div>
              </div>
            </label>
          ))}
          <div style={s.selCount}>{selGroups.length} nhóm được chọn</div>
        </div>
      </div>

      {/* Composer */}
      <div style={s.composer}>
        <div style={s.sectionTitle}><span>📝</span> Nội dung bài viết</div>
        <textarea
          style={s.textarea}
          placeholder="Nhập nội dung bài viết ở đây..."
          value={content}
          onChange={e => setContent(e.target.value)}
        />
        <div style={{ fontSize: 12, color: '#8a8d91', marginTop: 4, textAlign: 'right' }}>{content.length} ký tự</div>

        {imagePreview && (
          <div style={s.imagePreview}>
            <img src={imagePreview} alt="preview" style={s.imgThumb} />
            <button style={s.removeImg} onClick={removeImage}>✕</button>
          </div>
        )}

        <div style={s.toolRow}>
          <label style={s.uploadBtn}>
            🖼️ Đính kèm ảnh
            <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={onImage} />
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13 }}>
            <input type="checkbox" checked={useSchedule} onChange={e => setUseSchedule(e.target.checked)} />
            🕐 Lên lịch đăng
          </label>
        </div>

        {useSchedule && (
          <div style={s.scheduleRow}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>Thời gian:</span>
            <input
              type="datetime-local"
              style={s.scheduleInput}
              value={scheduleAt}
              onChange={e => setScheduleAt(e.target.value)}
              min={new Date().toISOString().slice(0, 16)}
            />
          </div>
        )}

        <div style={{ ...s.actionRow, marginTop: 16 }}>
          {useSchedule ? (
            <button style={{ ...s.btn, ...s.btnSchedule, ...(canPost ? {} : s.btnDisabled) }} onClick={handleSchedule}>
              🕐 Lên lịch đăng
            </button>
          ) : (
            <button style={{ ...s.btn, ...s.btnPost, ...(canPost ? {} : s.btnDisabled) }} onClick={handlePost} disabled={posting}>
              {posting ? '⏳ Đang đăng...' : '🚀 Đăng ngay'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
