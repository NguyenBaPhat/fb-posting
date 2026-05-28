import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { getAccounts, getGroups, sendPost, createSchedule, getPostJob, getTemplates, saveTemplate, deleteTemplate, templateImageUrl } from '../api'
import CheckList from '../components/CheckList'
import ProgressOverlay from '../components/ProgressOverlay'
import { pollJob } from '../utils/pollJob'

const s = {
  page: { maxWidth: 1200 },
  title: { fontSize: 24, fontWeight: 700, color: '#1877f2', marginBottom: 24 },
  modeTabs: { display: 'flex', gap: 0, marginBottom: 20, borderRadius: 10, overflow: 'hidden', border: '1.5px solid #e4e6ea', width: 'fit-content' },
  modeTab: { padding: '10px 24px', border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: 14, background: '#f7f8fa', color: '#65676b', transition: 'all 0.15s' },
  modeTabActive: { background: '#1877f2', color: '#fff' },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 },
  section: { background: '#fff', borderRadius: 12, padding: 20, boxShadow: '0 1px 4px rgba(0,0,0,0.1)' },
  checkSub: { fontSize: 12, color: '#65676b' },
  composer: { background: '#fff', borderRadius: 12, padding: 20, boxShadow: '0 1px 4px rgba(0,0,0,0.1)', marginBottom: 20 },
  textarea: { width: '100%', minHeight: 140, padding: '12px 14px', borderRadius: 8, border: '1.5px solid #e4e6ea', fontSize: 15, resize: 'vertical', outline: 'none', fontFamily: 'inherit', lineHeight: 1.5 },
  imagePreview: { marginTop: 12, position: 'relative', display: 'inline-block' },
  imgThumb: { maxHeight: 120, borderRadius: 8, border: '2px solid #e4e6ea' },
  removeImg: { position: 'absolute', top: -8, right: -8, background: '#d73a3a', color: '#fff', border: 'none', borderRadius: '50%', width: 22, height: 22, cursor: 'pointer', fontSize: 12 },
  toolRow: { display: 'flex', gap: 10, marginTop: 12, alignItems: 'center', flexWrap: 'wrap' },
  uploadBtn: { display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 8, border: '1.5px dashed #1877f2', background: '#e7f3ff', color: '#1877f2', cursor: 'pointer', fontSize: 13, fontWeight: 600 },
  scheduleBlock: { padding: '12px 0', borderTop: '1px solid #f0f2f5', marginTop: 12 },
  advancedBox: { background: '#f7f8fa', borderRadius: 8, padding: 14, marginTop: 10 },
  label: { fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 6 },
  select: { padding: '8px 12px', borderRadius: 8, border: '1.5px solid #e4e6ea', fontSize: 13, width: '100%', marginBottom: 10 },
  scheduleInput: { padding: '8px 12px', borderRadius: 8, border: '1.5px solid #e4e6ea', fontSize: 13, outline: 'none', width: '100%' },
  browserRow: { padding: '12px 0', borderTop: '1px solid #f0f2f5', marginTop: 12 },
  browserOption: { display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 8, cursor: 'pointer', fontSize: 13 },
  browserHint: { fontSize: 12, color: '#65676b', marginLeft: 24 },
  actionRow: { display: 'flex', gap: 12, justifyContent: 'flex-end' },
  btn: { padding: '10px 24px', borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 700, fontSize: 14 },
  btnPost: { background: '#1877f2', color: '#fff', minWidth: 140 },
  btnSchedule: { background: '#e7f3ff', color: '#1877f2', minWidth: 140 },
  btnDisabled: { opacity: 0.5, cursor: 'not-allowed' },
  mpFields: { background: '#fff8e1', borderRadius: 10, padding: '16px', marginBottom: 14, border: '1.5px solid #ffe082' },
  mpRow: { display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 12, marginBottom: 12 },
  mpInput: { padding: '9px 12px', borderRadius: 8, border: '1.5px solid #e4e6ea', fontSize: 14, outline: 'none', width: '100%', boxSizing: 'border-box' },
  mpSelect: { padding: '9px 12px', borderRadius: 8, border: '1.5px solid #e4e6ea', fontSize: 14, width: '100%', background: '#fff', boxSizing: 'border-box' },
}

const RECURRENCE_OPTIONS = [
  { value: 'once', label: 'Một lần' },
  { value: 'hourly', label: 'Lặp mỗi N giờ' },
  { value: 'daily', label: 'Hằng ngày (cùng giờ)' },
  { value: 'weekly', label: 'Hằng tuần (cùng thứ & giờ)' },
  { value: 'every_n_days', label: 'Mỗi N ngày' },
]

export default function Composer() {
  const [accounts, setAccounts] = useState([])
  const [groups, setGroups] = useState([])
  const [postMode, setPostMode] = useState('normal') // 'normal' | 'marketplace'
  const [selAccounts, setSelAccounts] = useState([])
  const [selGroups, setSelGroups] = useState([])
  const [charCount, setCharCount] = useState(0)
  const [images, setImages] = useState([])       // [{file, preview}]
  const [scheduleAt, setScheduleAt] = useState('')
  const [useSchedule, setUseSchedule] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [recurrence, setRecurrence] = useState('once')
  const [recurrenceInterval, setRecurrenceInterval] = useState(2)
  const [headless, setHeadless] = useState(true)
  const [posting, setPosting] = useState(false)
  const [job, setJob] = useState(null)
  // marketplace-specific fields
  const [mpTitle, setMpTitle] = useState('')
  const [mpPrice, setMpPrice] = useState('')
  const [mpCondition, setMpCondition] = useState('Mới')
  // template
  const [templates, setTemplates] = useState([])
  const [savingTemplate, setSavingTemplate] = useState(false)
  const [templateName, setTemplateName] = useState('')
  const fileRef = useRef()
  const contentRef = useRef()

  const loadTemplates = () => getTemplates().then(r => setTemplates(r.data)).catch(() => {})

  useEffect(() => {
    getAccounts().then(r => setAccounts(r.data)).catch(() => {})
    getGroups().then(r => setGroups(r.data)).catch(() => {})
    loadTemplates()
  }, [])

  const normalGroups = groups.filter(g => g.post_type !== 'marketplace')
  const marketplaceGroups = groups.filter(g => g.post_type === 'marketplace')
  const displayGroups = postMode === 'marketplace' ? marketplaceGroups : normalGroups

  const switchMode = (mode) => {
    setPostMode(mode)
    setSelGroups([])
  }

  const getContent = () => (contentRef.current?.value ?? '').trim()
  const syncCharCount = () => setCharCount(contentRef.current?.value?.length ?? 0)
  const totalTasks = selAccounts.length * selGroups.length

  const onImage = (e) => {
    const files = Array.from(e.target.files)
    if (!files.length) return
    const newEntries = files.map(f => ({ file: f, preview: URL.createObjectURL(f) }))
    setImages(prev => [...prev, ...newEntries])
    if (fileRef.current) fileRef.current.value = ''
  }
  const removeImage = (idx) => {
    setImages(prev => prev.filter((_, i) => i !== idx))
  }

  const validatePost = () => {
    if (selAccounts.length === 0) return 'Chọn ít nhất 1 tài khoản'
    if (selGroups.length === 0) return 'Chọn ít nhất 1 nhóm'
    if (postMode === 'marketplace') {
      if (!mpTitle.trim()) return 'Vui lòng nhập tên mặt hàng'
      if (!mpPrice.trim()) return 'Vui lòng nhập giá bán'
    } else {
      if (!getContent()) return 'Vui lòng nhập nội dung bài viết'
    }
    return null
  }

  const canPost = selAccounts.length > 0 && selGroups.length > 0 && (
    postMode === 'marketplace' ? (mpTitle.trim().length > 0 && mpPrice.trim().length > 0) : charCount > 0
  )

  const buildFormData = () => {
    const fd = new FormData()
    fd.append('content', getContent())
    fd.append('account_ids', selAccounts.join(','))
    fd.append('group_ids', selGroups.join(','))
    fd.append('headless', headless ? 'true' : 'false')
    fd.append('post_type', postMode)
    if (postMode === 'marketplace') {
      fd.append('mp_title', mpTitle.trim())
      fd.append('mp_price', mpPrice.trim())
      fd.append('mp_condition', mpCondition)
    }
    images.forEach(({ file }) => fd.append('images', file))
    return fd
  }

  const resetForm = () => {
    if (contentRef.current) contentRef.current.value = ''
    setCharCount(0)
    setImages([])
    if (postMode === 'marketplace') {
      setMpTitle('')
      setMpPrice('')
      setMpCondition('Mới')
    }
  }

  const handleSaveTemplate = async () => {
    const name = templateName.trim()
    if (!name) { toast.error('Nhập tên template'); return }
    const content = getContent()
    const isMP = postMode === 'marketplace'
    if (!content && images.length === 0 && !mpTitle.trim()) {
      toast.error('Chưa có nội dung, ảnh hoặc thông tin để lưu'); return
    }
    try {
      const fd = new FormData()
      fd.append('name', name)
      fd.append('content', content)
      fd.append('post_type', postMode)
      if (isMP) {
        fd.append('mp_title', mpTitle.trim())
        fd.append('mp_price', mpPrice.trim())
        fd.append('mp_condition', mpCondition)
      }
      images.forEach(({ file }) => fd.append('images', file))
      await saveTemplate(fd)
      toast.success(`Đã lưu template "${name}"`)
      setTemplateName('')
      setSavingTemplate(false)
      loadTemplates()
    } catch {
      toast.error('Lỗi khi lưu template')
    }
  }

  const handleApplyTemplate = async (tmpl) => {
    // Chuyển mode nếu cần
    if (tmpl.post_type && tmpl.post_type !== postMode) {
      switchMode(tmpl.post_type)
    }
    // Điền nội dung
    if (contentRef.current) {
      contentRef.current.value = tmpl.content || ''
      setCharCount((tmpl.content || '').length)
    }
    // Điền marketplace fields
    if (tmpl.post_type === 'marketplace') {
      setMpTitle(tmpl.mp_title || '')
      setMpPrice(tmpl.mp_price || '')
      setMpCondition(tmpl.mp_condition || 'Mới')
    }
    // Tải ảnh
    if (tmpl.image_filenames?.length > 0) {
      try {
        const entries = await Promise.all(
          tmpl.image_filenames.map(async (filename) => {
            const res = await fetch(templateImageUrl(filename))
            const blob = await res.blob()
            const file = new File([blob], filename, { type: blob.type })
            return { file, preview: URL.createObjectURL(blob) }
          })
        )
        setImages(entries)
      } catch {
        toast.error('Không tải được ảnh từ template')
      }
    } else {
      setImages([])
    }
    toast.success(`Đã áp dụng template "${tmpl.name}"`)
  }

  const handleDeleteTemplate = async (id, name) => {
    if (!confirm(`Xóa template "${name}"?`)) return
    try {
      await deleteTemplate(id)
      toast.success('Đã xóa template')
      loadTemplates()
    } catch {
      toast.error('Lỗi khi xóa template')
    }
  }

  const handlePost = async () => {
    const err = validatePost()
    if (err) { toast.error(err); return }
    setPosting(true)
    setJob({ status: 'running', done: 0, total: totalTasks, results: [], current: null })
    try {
      const fd = buildFormData()
      const start = await sendPost(fd)
      const { job_id, total } = start.data
      setJob({ status: 'running', done: 0, total, results: [], current: null })
      const finished = await pollJob(getPostJob, job_id, setJob)
      const record = finished.record || {}
      const { success_count = 0, total: t = 0 } = record
      if (success_count === t) toast.success(`✅ Đăng bài thành công ${success_count}/${t}!`)
      else if (success_count > 0) toast.success(`⚠️ Thành công ${success_count}/${t}`)
      else toast.error(`❌ Đăng bài thất bại cả ${t} nhóm`)
      resetForm()
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || 'Lỗi đăng bài')
    } finally {
      setPosting(false)
      setJob(null)
    }
  }

  const handleSchedule = async () => {
    const err = validatePost()
    if (err) { toast.error(err); return }
    if (!scheduleAt) { toast.error('Vui lòng chọn thời gian đăng bài'); return }
    try {
      const fd = buildFormData()
      fd.append('scheduled_at', scheduleAt.length === 16 ? `${scheduleAt}:00` : scheduleAt)
      fd.append('recurrence', recurrence)
      fd.append('recurrence_interval', String(recurrenceInterval))
      await createSchedule(fd)
      const recLabel = RECURRENCE_OPTIONS.find(o => o.value === recurrence)?.label || recurrence
      toast.success(recurrence === 'once' ? '✅ Đã lên lịch đăng bài!' : `✅ Đã lên lịch: ${recLabel}`)
      resetForm()
      setUseSchedule(false)
      setScheduleAt('')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Lỗi khi lên lịch')
    }
  }

  const needsInterval = recurrence === 'hourly' || recurrence === 'every_n_days'

  return (
    <div style={s.page}>
      <ProgressOverlay
        visible={posting && job}
        title="Đang đăng bài..."
        subtitle={headless
          ? 'Hệ thống đang tự động đăng nhập và đăng bài...'
          : 'Chrome đang mở — hoàn thành 2FA trong cửa sổ nếu cần'}
        done={job?.done ?? 0}
        total={job?.total ?? totalTasks}
        results={job?.results ?? []}
        current={job?.current}
      />

      <h1 style={s.title}>✍️ Soạn & Đăng bài</h1>

      {/* Mode tabs */}
      <div style={s.modeTabs}>
        <button
          style={{ ...s.modeTab, ...(postMode === 'normal' ? s.modeTabActive : {}) }}
          onClick={() => switchMode('normal')}
        >
          📝 Đăng thường
        </button>
        <button
          style={{ ...s.modeTab, ...(postMode === 'marketplace' ? s.modeTabActive : {}) }}
          onClick={() => switchMode('marketplace')}
        >
          🏪 Marketplace (Mua &amp; Bán)
        </button>
      </div>

      <div style={s.grid}>
        <div style={s.section}>
          <CheckList
            title="Tài khoản đăng bài"
            icon="👤"
            items={accounts}
            selected={selAccounts}
            onToggle={(id) => setSelAccounts(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id])}
            onSelectAll={setSelAccounts}
            emptyText={<>Chưa có tài khoản. <a href="/accounts">Thêm ngay</a></>}
            renderItem={(acc) => (
              <div>
                <div style={{ fontSize: 14, fontWeight: 500 }}>{acc.name}</div>
                <div style={s.checkSub}>{acc.email}</div>
              </div>
            )}
          />
        </div>

        <div style={s.section}>
          <CheckList
            title={postMode === 'marketplace' ? 'Nhóm Marketplace' : 'Nhóm đăng bài'}
            icon={postMode === 'marketplace' ? '🏪' : '👥'}
            items={displayGroups}
            selected={selGroups}
            onToggle={(id) => setSelGroups(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id])}
            onSelectAll={setSelGroups}
            emptyText={<>Chưa có nhóm. <a href="/groups">Thêm ngay</a></>}
            renderItem={(g) => (
              <div>
                <div style={{ fontSize: 14, fontWeight: 500 }}>{g.name}</div>
                <div style={s.checkSub} title={g.url}>
                  {g.url.replace('https://www.facebook.com/groups/', 'groups/')}
                </div>
              </div>
            )}
          />
        </div>
      </div>

      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
      <div style={{ flex: 1, minWidth: 0 }}>
      <div style={s.composer}>
        {postMode === 'marketplace' && (
          <div style={s.mpFields}>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12, color: '#e65100' }}>
              🏷️ Thông tin niêm yết
            </div>
            <div style={s.mpRow}>
              <div>
                <label style={s.label}>Tên mặt hàng *</label>
                <input
                  style={s.mpInput}
                  placeholder="VD: Xe máy Honda Wave, Tủ lạnh Samsung..."
                  value={mpTitle}
                  onChange={e => setMpTitle(e.target.value)}
                />
              </div>
              <div>
                <label style={s.label}>Giá bán (đ) *</label>
                <input
                  style={s.mpInput}
                  placeholder="VD: 5000000"
                  value={mpPrice}
                  onChange={e => setMpPrice(e.target.value.replace(/[^0-9]/g, ''))}
                  inputMode="numeric"
                />
              </div>
              <div>
                <label style={s.label}>Tình trạng</label>
                <select style={s.mpSelect} value={mpCondition} onChange={e => setMpCondition(e.target.value)}>
                  <option value="Mới">Mới</option>
                  <option value="Đã qua sử dụng - Như mới">Đã qua sử dụng - Như mới</option>
                  <option value="Đã qua sử dụng - Tốt">Đã qua sử dụng - Tốt</option>
                  <option value="Đã qua sử dụng - Khá tốt">Đã qua sử dụng - Khá tốt</option>
                </select>
              </div>
            </div>
          </div>
        )}

        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 14 }}>
          {postMode === 'marketplace' ? '📝 Mô tả mặt hàng' : '📝 Nội dung bài viết'}
        </div>
        <textarea
          ref={contentRef}
          style={s.textarea}
          placeholder={postMode === 'marketplace'
            ? 'Nhập mô tả chi tiết về mặt hàng (không bắt buộc)...'
            : 'Nhập nội dung bài viết ở đây...'}
          defaultValue=""
          onInput={syncCharCount}
          onCompositionEnd={syncCharCount}
        />
        <div style={{ fontSize: 12, color: '#8a8d91', marginTop: 4, textAlign: 'right' }}>
          {charCount} ký tự · {totalTasks} lượt đăng (TK × nhóm)
        </div>

        {images.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 12 }}>
            {images.map((img, idx) => (
              <div key={idx} style={s.imagePreview}>
                <img src={img.preview} alt={`preview-${idx}`} style={s.imgThumb} />
                <button type="button" style={s.removeImg} onClick={() => removeImage(idx)}>✕</button>
              </div>
            ))}
          </div>
        )}

        <div style={s.toolRow}>
          <label style={s.uploadBtn}>
            🖼️ Đính kèm ảnh
            <input ref={fileRef} type="file" accept="image/*" multiple style={{ display: 'none' }} onChange={onImage} />
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13 }}>
            <input type="checkbox" checked={useSchedule} onChange={e => setUseSchedule(e.target.checked)} />
            🕐 Lên lịch đăng
          </label>
        </div>

        {useSchedule && (
          <div style={s.scheduleBlock}>
            <label style={s.label}>Thời gian bắt đầu</label>
            <input
              type="datetime-local"
              style={s.scheduleInput}
              value={scheduleAt}
              onChange={e => setScheduleAt(e.target.value)}
            />

            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12, fontSize: 13, cursor: 'pointer' }}>
              <input type="checkbox" checked={showAdvanced} onChange={e => setShowAdvanced(e.target.checked)} />
              ⚙️ Tùy chọn nâng cao (lặp lại)
            </label>

            {showAdvanced && (
              <div style={s.advancedBox}>
                <label style={s.label}>Tần suất</label>
                <select style={s.select} value={recurrence} onChange={e => setRecurrence(e.target.value)}>
                  {RECURRENCE_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
                {needsInterval && (
                  <>
                    <label style={s.label}>
                      {recurrence === 'hourly' ? 'Số giờ giữa mỗi lần' : 'Số ngày giữa mỗi lần'}
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={recurrence === 'hourly' ? 24 : 30}
                      style={s.scheduleInput}
                      value={recurrenceInterval}
                      onChange={e => setRecurrenceInterval(Number(e.target.value) || 1)}
                    />
                  </>
                )}
                <div style={{ fontSize: 12, color: '#65676b', marginTop: 8 }}>
                  {recurrence === 'hourly' && `Đăng lại mỗi ${recurrenceInterval} giờ kể từ thời điểm bắt đầu.`}
                  {recurrence === 'daily' && 'Đăng mỗi ngày vào đúng giờ đã chọn.'}
                  {recurrence === 'weekly' && 'Đăng mỗi tuần vào cùng thứ và giờ.'}
                  {recurrence === 'every_n_days' && `Đăng lại mỗi ${recurrenceInterval} ngày.`}
                </div>
              </div>
            )}
          </div>
        )}

        <div style={s.browserRow}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>🌐 Chế độ trình duyệt</div>
          <label style={s.browserOption}>
            <input type="radio" name="browserMode" checked={headless} onChange={() => setHeadless(true)} />
            <div><div>Chạy ngầm</div><div style={s.browserHint}>Không hiện cửa sổ Chrome</div></div>
          </label>
          <label style={s.browserOption}>
            <input type="radio" name="browserMode" checked={!headless} onChange={() => setHeadless(false)} />
            <div><div>Hiện trình duyệt</div><div style={s.browserHint}>Mở Chrome để xem & xử lý 2FA</div></div>
          </label>
        </div>

        <div style={{ ...s.actionRow, marginTop: 16 }}>
          {useSchedule ? (
            <button type="button" style={{ ...s.btn, ...s.btnSchedule, ...(!canPost ? s.btnDisabled : {}) }} onClick={handleSchedule} disabled={posting}>
              🕐 Lên lịch đăng
            </button>
          ) : (
            <button type="button" style={{ ...s.btn, ...s.btnPost, ...(!canPost ? s.btnDisabled : {}) }} onClick={handlePost} disabled={posting}>
              {posting ? '⏳ Đang đăng...' : (postMode === 'marketplace' ? '🏪 Đăng niêm yết' : '🚀 Đăng ngay')}
            </button>
          )}
        </div>
      </div>
      </div>{/* end s.composer wrapper */}

      {/* ── Template Panel ── */}
      <div style={{
        width: 260, flexShrink: 0,
        background: '#fff', borderRadius: 12, padding: 16,
        boxShadow: '0 1px 4px rgba(0,0,0,0.1)',
        maxHeight: 600, display: 'flex', flexDirection: 'column',
      }}>
        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>📋 Templates</span>
          {!savingTemplate && (
            <button
              onClick={() => { setSavingTemplate(true); setTemplateName('') }}
              style={{
                padding: '4px 10px', borderRadius: 8, border: 'none', cursor: 'pointer',
                fontSize: 12, fontWeight: 600, background: '#e7f3ff', color: '#1877f2',
              }}
            >
              + Lưu mới
            </button>
          )}
        </div>

        {savingTemplate && (
          <div style={{ marginBottom: 12, background: '#f7f8fa', borderRadius: 8, padding: 10 }}>
            <input
              autoFocus
              placeholder="Tên template..."
              value={templateName}
              onChange={e => setTemplateName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSaveTemplate()}
              style={{
                width: '100%', padding: '7px 10px', borderRadius: 6,
                border: '1.5px solid #e4e6ea', fontSize: 13, outline: 'none',
                boxSizing: 'border-box', marginBottom: 8,
              }}
            />
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                onClick={handleSaveTemplate}
                style={{ flex: 1, padding: '6px 0', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600, background: '#1877f2', color: '#fff' }}
              >
                💾 Lưu
              </button>
              <button
                onClick={() => setSavingTemplate(false)}
                style={{ flex: 1, padding: '6px 0', borderRadius: 6, border: '1px solid #e4e6ea', cursor: 'pointer', fontSize: 12, fontWeight: 600, background: '#fff', color: '#65676b' }}
              >
                Hủy
              </button>
            </div>
          </div>
        )}

        <div style={{ overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {templates.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#aaa', fontSize: 13, marginTop: 24 }}>
              Chưa có template nào
            </div>
          ) : templates.map(tmpl => (
            <div
              key={tmpl.id}
              onClick={() => handleApplyTemplate(tmpl)}
              style={{
                border: '1.5px solid #e4e6ea', borderRadius: 8, padding: '10px',
                cursor: 'pointer', transition: 'border-color 0.15s',
              }}
              onMouseEnter={e => e.currentTarget.style.borderColor = '#1877f2'}
              onMouseLeave={e => e.currentTarget.style.borderColor = '#e4e6ea'}
            >
              {/* Header: tên + nút xóa */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#1877f2' }}>{tmpl.name}</div>
                <button
                  onClick={e => { e.stopPropagation(); handleDeleteTemplate(tmpl.id, tmpl.name) }}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#d73a3a', fontSize: 14, padding: '0 2px', lineHeight: 1 }}
                  title="Xóa template"
                >✕</button>
              </div>

              {/* Loại */}
              <div style={{ fontSize: 11, marginBottom: 4 }}>
                <span style={{
                  background: tmpl.post_type === 'marketplace' ? '#fff8e1' : '#e7f3ff',
                  color: tmpl.post_type === 'marketplace' ? '#e65100' : '#1877f2',
                  padding: '1px 6px', borderRadius: 10, fontWeight: 600,
                }}>
                  {tmpl.post_type === 'marketplace' ? '🏪 Marketplace' : '📝 Đăng thường'}
                </span>
              </div>

              {/* Marketplace fields */}
              {tmpl.post_type === 'marketplace' && tmpl.mp_title && (
                <div style={{ fontSize: 12, color: '#1c1e21', marginBottom: 3 }}>
                  <b>Tên:</b> {tmpl.mp_title}
                </div>
              )}
              {tmpl.post_type === 'marketplace' && tmpl.mp_price && (
                <div style={{ fontSize: 12, color: '#1c1e21', marginBottom: 3 }}>
                  <b>Giá:</b> {Number(tmpl.mp_price).toLocaleString('vi-VN')} đ · {tmpl.mp_condition}
                </div>
              )}

              {/* Nội dung */}
              {tmpl.content && (
                <div style={{
                  fontSize: 12, color: '#65676b', marginTop: 4,
                  whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  background: '#f7f8fa', borderRadius: 6,
                  padding: '6px 8px', maxHeight: 120, overflowY: 'auto',
                }}>
                  {tmpl.content}
                </div>
              )}

              {/* Ảnh thumbnails */}
              {tmpl.image_filenames?.length > 0 && (
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 6 }}>
                  {tmpl.image_filenames.map(fn => (
                    <img
                      key={fn}
                      src={templateImageUrl(fn)}
                      alt=""
                      style={{ width: 44, height: 44, objectFit: 'cover', borderRadius: 4, border: '1px solid #e4e6ea' }}
                    />
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      </div>{/* end flex row */}
    </div>
  )
}
