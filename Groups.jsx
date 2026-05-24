import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { getGroups, createGroup, deleteGroup } from '../api'

const s = {
  page: { maxWidth: 800 },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 },
  title: { fontSize: 24, fontWeight: 700, color: '#1877f2' },
  card: {
    background: '#fff', borderRadius: 12, padding: 20,
    boxShadow: '0 1px 4px rgba(0,0,0,0.1)', marginBottom: 12,
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  },
  icon: {
    width: 44, height: 44, borderRadius: 12,
    background: 'linear-gradient(135deg,#42b0ff,#1877f2)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 22, marginRight: 16, flexShrink: 0,
  },
  info: { flex: 1 },
  name: { fontWeight: 600, fontSize: 15, color: '#1c1e21' },
  url: { fontSize: 12, color: '#65676b', marginTop: 2, wordBreak: 'break-all' },
  desc: { fontSize: 12, color: '#8a8d91', marginTop: 4 },
  btn: { padding: '8px 16px', borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: 13 },
  btnPrimary: { background: '#1877f2', color: '#fff' },
  btnDanger: { background: '#ffebe9', color: '#d73a3a' },
  modal: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 999 },
  modalBox: { background: '#fff', borderRadius: 16, padding: 32, width: 460, boxShadow: '0 20px 60px rgba(0,0,0,0.25)' },
  field: { marginBottom: 16 },
  label: { display: 'block', fontWeight: 600, fontSize: 13, marginBottom: 6, color: '#1c1e21' },
  input: { width: '100%', padding: '10px 14px', borderRadius: 8, border: '1.5px solid #e4e6ea', fontSize: 14, outline: 'none' },
  textarea: { width: '100%', padding: '10px 14px', borderRadius: 8, border: '1.5px solid #e4e6ea', fontSize: 14, outline: 'none', resize: 'vertical', minHeight: 72 },
  row: { display: 'flex', gap: 10, marginTop: 20 },
  empty: { textAlign: 'center', padding: 60, color: '#65676b' },
  hint: { fontSize: 11, color: '#8a8d91', marginTop: 4 },
}

const initForm = { name: '', url: '', description: '' }

export default function Groups() {
  const [groups, setGroups] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState(initForm)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    try {
      const res = await getGroups()
      setGroups(res.data)
    } catch { toast.error('Không tải được danh sách nhóm') }
  }

  useEffect(() => { load() }, [])

  const submit = async (e) => {
    e.preventDefault()
    if (!form.name || !form.url) {
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
    } finally { setLoading(false) }
  }

  const remove = async (id, name) => {
    if (!confirm(`Xóa nhóm "${name}"?`)) return
    try {
      await deleteGroup(id)
      toast.success('Đã xóa nhóm')
      load()
    } catch { toast.error('Không xóa được nhóm') }
  }

  return (
    <div style={s.page}>
      <div style={s.header}>
        <h1 style={s.title}>👥 Nhóm Facebook</h1>
        <button style={{ ...s.btn, ...s.btnPrimary }} onClick={() => setShowModal(true)}>
          + Thêm nhóm
        </button>
      </div>

      {groups.length === 0 ? (
        <div style={s.empty}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>👥</div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>Chưa có nhóm nào</div>
          <div style={{ fontSize: 13, marginTop: 6 }}>Thêm nhóm Facebook để đăng bài tự động</div>
        </div>
      ) : (
        groups.map((g) => (
          <div key={g.id} style={s.card}>
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <div style={s.icon}>👥</div>
              <div style={s.info}>
                <div style={s.name}>{g.name}</div>
                <div style={s.url}>{g.url}</div>
                {g.description && <div style={s.desc}>{g.description}</div>}
              </div>
            </div>
            <button style={{ ...s.btn, ...s.btnDanger }} onClick={() => remove(g.id, g.name)}>
              Xóa
            </button>
          </div>
        ))
      )}

      {showModal && (
        <div style={s.modal} onClick={(e) => e.target === e.currentTarget && setShowModal(false)}>
          <div style={s.modalBox}>
            <h2 style={{ marginBottom: 24, fontSize: 20, fontWeight: 700 }}>Thêm nhóm Facebook</h2>
            <form onSubmit={submit}>
              <div style={s.field}>
                <label style={s.label}>Tên nhóm</label>
                <input style={s.input} placeholder="VD: Nhóm bán hàng HCM"
                  value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
              </div>
              <div style={s.field}>
                <label style={s.label}>URL nhóm</label>
                <input style={s.input} placeholder="https://www.facebook.com/groups/..."
                  value={form.url} onChange={e => setForm({ ...form, url: e.target.value })} />
                <div style={s.hint}>Dán đường dẫn URL của nhóm Facebook</div>
              </div>
              <div style={s.field}>
                <label style={s.label}>Mô tả (tùy chọn)</label>
                <textarea style={s.textarea} placeholder="Ghi chú về nhóm này..."
                  value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
              </div>
              <div style={s.row}>
                <button type="button" style={{ ...s.btn, flex: 1, background: '#f0f2f5', color: '#1c1e21' }}
                  onClick={() => setShowModal(false)}>Hủy</button>
                <button type="submit" style={{ ...s.btn, ...s.btnPrimary, flex: 2 }} disabled={loading}>
                  {loading ? 'Đang lưu...' : 'Thêm nhóm'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
