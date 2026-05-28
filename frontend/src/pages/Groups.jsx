import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { getGroups, createGroup, deleteGroup } from '../api'

const TAB_NORMAL = 'normal'
const TAB_MP = 'marketplace'

const s = {
  page: { maxWidth: 800 },
  // ── Header ────────────────────────────────────────────────
  header: {
    display: 'flex', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: 20,
  },
  title: { fontSize: 24, fontWeight: 700, color: '#1877f2' },
  addBtn: {
    padding: '9px 20px', borderRadius: 9, border: 'none',
    cursor: 'pointer', fontWeight: 700, fontSize: 14,
    background: '#1877f2', color: '#fff',
    display: 'flex', alignItems: 'center', gap: 6,
  },
  // ── Tabs ──────────────────────────────────────────────────
  tabBar: {
    display: 'flex', borderBottom: '2px solid #e4e6ea',
    marginBottom: 20, gap: 0,
  },
  tab: {
    padding: '11px 24px', border: 'none', background: 'transparent',
    cursor: 'pointer', fontWeight: 600, fontSize: 14, color: '#65676b',
    borderBottom: '3px solid transparent', marginBottom: -2,
    display: 'flex', alignItems: 'center', gap: 8, transition: 'color 0.15s',
  },
  tabActiveNormal: { color: '#1877f2', borderBottomColor: '#1877f2' },
  tabActiveMP: { color: '#e65100', borderBottomColor: '#e65100' },
  badge: {
    fontSize: 11, fontWeight: 700, padding: '2px 8px',
    borderRadius: 20, minWidth: 20, textAlign: 'center',
  },
  badgeNormal: { background: '#e7f3ff', color: '#1877f2' },
  badgeMP: { background: '#fff3e0', color: '#e65100' },
  badgeInactive: { background: '#f0f2f5', color: '#8a8d91' },
  // ── Group card ────────────────────────────────────────────
  card: {
    background: '#fff', borderRadius: 12, padding: '13px 18px',
    boxShadow: '0 1px 3px rgba(0,0,0,0.08)', marginBottom: 8,
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    transition: 'box-shadow 0.15s',
  },
  iconNormal: {
    width: 38, height: 38, borderRadius: 10, flexShrink: 0,
    background: 'linear-gradient(135deg,#42b0ff,#1877f2)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 18, marginRight: 14,
  },
  iconMP: {
    width: 38, height: 38, borderRadius: 10, flexShrink: 0,
    background: 'linear-gradient(135deg,#ffb74d,#e65100)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 18, marginRight: 14,
  },
  info: { flex: 1, minWidth: 0 },
  name: { fontWeight: 600, fontSize: 14, color: '#1c1e21', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' },
  url: { fontSize: 12, color: '#65676b', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' },
  desc: { fontSize: 12, color: '#8a8d91', marginTop: 2 },
  delBtn: {
    padding: '6px 14px', borderRadius: 8, border: 'none',
    cursor: 'pointer', fontWeight: 600, fontSize: 13,
    background: '#ffebe9', color: '#d73a3a', flexShrink: 0, marginLeft: 12,
  },
  // ── Empty state ───────────────────────────────────────────
  empty: {
    textAlign: 'center', padding: '48px 0', color: '#aaa',
  },
  // ── Modal ─────────────────────────────────────────────────
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 999,
  },
  modal: {
    background: '#fff', borderRadius: 16, padding: '28px 32px',
    width: 480, boxShadow: '0 20px 60px rgba(0,0,0,0.22)',
  },
  modalTitle: { fontSize: 20, fontWeight: 700, marginBottom: 20 },
  field: { marginBottom: 16 },
  label: { display: 'block', fontWeight: 600, fontSize: 13, marginBottom: 6, color: '#1c1e21' },
  input: {
    width: '100%', padding: '10px 14px', borderRadius: 8,
    border: '1.5px solid #e4e6ea', fontSize: 14, outline: 'none', boxSizing: 'border-box',
  },
  textarea: {
    width: '100%', padding: '10px 14px', borderRadius: 8,
    border: '1.5px solid #e4e6ea', fontSize: 14, outline: 'none',
    resize: 'vertical', minHeight: 64, boxSizing: 'border-box',
  },
  hint: { fontSize: 11, color: '#8a8d91', marginTop: 4 },
  typeTabs: {
    display: 'flex', borderRadius: 9, overflow: 'hidden',
    border: '1.5px solid #e4e6ea', marginBottom: 4,
  },
  typeTab: {
    flex: 1, padding: '9px 0', border: 'none', cursor: 'pointer',
    fontWeight: 600, fontSize: 13, background: '#f7f8fa', color: '#65676b',
  },
  typeTabActiveNormal: { background: '#1877f2', color: '#fff' },
  typeTabActiveMP: { background: '#e65100', color: '#fff' },
  modalActions: { display: 'flex', gap: 10, marginTop: 20 },
  cancelBtn: {
    flex: 1, padding: '10px 0', borderRadius: 8, border: 'none',
    cursor: 'pointer', fontWeight: 600, fontSize: 14,
    background: '#f0f2f5', color: '#1c1e21',
  },
  submitBtn: {
    flex: 2, padding: '10px 0', borderRadius: 8, border: 'none',
    cursor: 'pointer', fontWeight: 700, fontSize: 14, color: '#fff',
  },
}

const initForm = { name: '', url: '', description: '', post_type: TAB_NORMAL }

export default function Groups() {
  const [groups, setGroups] = useState([])
  const [activeTab, setActiveTab] = useState(TAB_NORMAL)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState(initForm)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    try {
      const res = await getGroups()
      setGroups(res.data)
    } catch {
      toast.error('Không tải được danh sách nhóm')
    }
  }

  useEffect(() => { load() }, [])

  const normalGroups = groups.filter(g => g.post_type !== TAB_MP)
  const marketplaceGroups = groups.filter(g => g.post_type === TAB_MP)
  const visibleGroups = activeTab === TAB_MP ? marketplaceGroups : normalGroups

  const openAddModal = () => {
    setForm({ ...initForm, post_type: activeTab })
    setShowModal(true)
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!form.name.trim() || !form.url.trim()) {
      toast.error('Vui lòng điền tên và URL nhóm')
      return
    }
    setLoading(true)
    try {
      await createGroup(form)
      toast.success('Đã thêm nhóm!')
      setShowModal(false)
      setForm(initForm)
      load()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Lỗi khi thêm nhóm')
    } finally {
      setLoading(false)
    }
  }

  const remove = async (id, name) => {
    if (!confirm(`Xóa nhóm "${name}"?`)) return
    try {
      await deleteGroup(id)
      toast.success('Đã xóa nhóm')
      load()
    } catch {
      toast.error('Không xóa được nhóm')
    }
  }

  const isMP = activeTab === TAB_MP

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <h1 style={s.title}>👥 Nhóm Facebook</h1>
        <button style={s.addBtn} onClick={openAddModal}>
          + Thêm nhóm
        </button>
      </div>

      {/* Tabs */}
      <div style={s.tabBar}>
        <button
          style={{
            ...s.tab,
            ...(activeTab === TAB_NORMAL ? s.tabActiveNormal : {}),
          }}
          onClick={() => setActiveTab(TAB_NORMAL)}
        >
          📝 Đăng thường
          <span style={{
            ...s.badge,
            ...(activeTab === TAB_NORMAL ? s.badgeNormal : s.badgeInactive),
          }}>
            {normalGroups.length}
          </span>
        </button>
        <button
          style={{
            ...s.tab,
            ...(activeTab === TAB_MP ? s.tabActiveMP : {}),
          }}
          onClick={() => setActiveTab(TAB_MP)}
        >
          🏪 Marketplace
          <span style={{
            ...s.badge,
            ...(activeTab === TAB_MP ? s.badgeMP : s.badgeInactive),
          }}>
            {marketplaceGroups.length}
          </span>
        </button>
      </div>

      {/* Group list */}
      {visibleGroups.length === 0 ? (
        <div style={s.empty}>
          <div style={{ fontSize: 40, marginBottom: 10 }}>{isMP ? '🏪' : '👥'}</div>
          <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>
            Chưa có nhóm {isMP ? 'Marketplace' : 'đăng thường'}
          </div>
          <div style={{ fontSize: 13 }}>
            Nhấn <strong>+ Thêm nhóm</strong> để thêm vào danh sách
          </div>
        </div>
      ) : (
        visibleGroups.map(g => (
          <div key={g.id} style={s.card}>
            <div style={{ display: 'flex', alignItems: 'center', minWidth: 0 }}>
              <div style={isMP ? s.iconMP : s.iconNormal}>
                {isMP ? '🏪' : '👥'}
              </div>
              <div style={s.info}>
                <div style={s.name}>{g.name}</div>
                <div style={s.url} title={g.url}>
                  {g.url.replace('https://www.facebook.com/groups/', 'groups/')}
                </div>
                {g.description && <div style={s.desc}>{g.description}</div>}
              </div>
            </div>
            <button style={s.delBtn} onClick={() => remove(g.id, g.name)}>
              Xóa
            </button>
          </div>
        ))
      )}

      {/* Add modal */}
      {showModal && (
        <div style={s.overlay} onClick={e => e.target === e.currentTarget && setShowModal(false)}>
          <div style={s.modal}>
            <div style={s.modalTitle}>Thêm nhóm Facebook</div>
            <form onSubmit={submit}>

              <div style={s.field}>
                <label style={s.label}>Loại nhóm</label>
                <div style={s.typeTabs}>
                  <button
                    type="button"
                    style={{ ...s.typeTab, ...(form.post_type === TAB_NORMAL ? s.typeTabActiveNormal : {}) }}
                    onClick={() => setForm({ ...form, post_type: TAB_NORMAL })}
                  >
                    📝 Đăng thường
                  </button>
                  <button
                    type="button"
                    style={{ ...s.typeTab, ...(form.post_type === TAB_MP ? s.typeTabActiveMP : {}) }}
                    onClick={() => setForm({ ...form, post_type: TAB_MP })}
                  >
                    🏪 Marketplace
                  </button>
                </div>
                <div style={s.hint}>
                  {form.post_type === TAB_MP
                    ? 'Nhóm Mua & Bán — đăng theo dạng niêm yết mặt hàng (tiêu đề, giá, tình trạng)'
                    : 'Nhóm thông thường — đăng bài viết với nội dung văn bản'}
                </div>
              </div>

              <div style={s.field}>
                <label style={s.label}>Tên nhóm</label>
                <input
                  style={s.input}
                  placeholder="VD: Nhóm bán hàng HCM"
                  value={form.name}
                  onChange={e => setForm({ ...form, name: e.target.value })}
                  autoFocus
                />
              </div>

              <div style={s.field}>
                <label style={s.label}>URL nhóm</label>
                <input
                  style={s.input}
                  placeholder="https://www.facebook.com/groups/..."
                  value={form.url}
                  onChange={e => setForm({ ...form, url: e.target.value })}
                />
                <div style={s.hint}>Dán đường dẫn URL của nhóm Facebook</div>
              </div>

              <div style={s.field}>
                <label style={s.label}>Mô tả <span style={{ fontWeight: 400, color: '#8a8d91' }}>(tùy chọn)</span></label>
                <textarea
                  style={s.textarea}
                  placeholder="Ghi chú về nhóm này..."
                  value={form.description}
                  onChange={e => setForm({ ...form, description: e.target.value })}
                />
              </div>

              <div style={s.modalActions}>
                <button type="button" style={s.cancelBtn} onClick={() => setShowModal(false)}>
                  Hủy
                </button>
                <button
                  type="submit"
                  style={{
                    ...s.submitBtn,
                    background: form.post_type === TAB_MP ? '#e65100' : '#1877f2',
                    opacity: loading ? 0.7 : 1,
                  }}
                  disabled={loading}
                >
                  {loading ? 'Đang lưu...' : (form.post_type === TAB_MP ? '🏪 Thêm nhóm Marketplace' : '📝 Thêm nhóm thường')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
