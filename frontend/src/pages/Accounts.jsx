import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { getAccounts, createAccount, deleteAccount } from '../api'

const s = {
  page: { maxWidth: 800 },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 },
  title: { fontSize: 24, fontWeight: 700, color: '#1877f2' },
  card: {
    background: '#fff', borderRadius: 12, padding: 20,
    boxShadow: '0 1px 4px rgba(0,0,0,0.1)', marginBottom: 12,
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  },
  avatar: {
    width: 44, height: 44, borderRadius: '50%',
    background: 'linear-gradient(135deg,#1877f2,#42b0ff)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#fff', fontWeight: 700, fontSize: 18, marginRight: 16, flexShrink: 0,
  },
  info: { flex: 1 },
  name: { fontWeight: 600, fontSize: 15, color: '#1c1e21' },
  email: { fontSize: 13, color: '#65676b', marginTop: 2 },
  badge: {
    fontSize: 11, padding: '2px 8px', borderRadius: 12,
    background: '#e7f3ff', color: '#1877f2', fontWeight: 600, marginLeft: 8,
  },
  btn: {
    padding: '8px 16px', borderRadius: 8, border: 'none',
    cursor: 'pointer', fontWeight: 600, fontSize: 13,
  },
  btnPrimary: { background: '#1877f2', color: '#fff' },
  btnDanger: { background: '#ffebe9', color: '#d73a3a' },
  modal: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 999,
  },
  modalBox: {
    background: '#fff', borderRadius: 16, padding: 32, width: 440,
    boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
  },
  field: { marginBottom: 16 },
  label: { display: 'block', fontWeight: 600, fontSize: 13, marginBottom: 6, color: '#1c1e21' },
  input: {
    width: '100%', padding: '10px 14px', borderRadius: 8,
    border: '1.5px solid #e4e6ea', fontSize: 14, outline: 'none',
  },
  row: { display: 'flex', gap: 10, marginTop: 20 },
  checkRow: { display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 10 },
  radioGroup: { marginBottom: 16 },
  radioHint: { fontSize: 12, color: '#65676b', marginTop: 4, marginLeft: 24 },
  badgeHidden: {
    fontSize: 11, padding: '2px 8px', borderRadius: 12,
    background: '#f0f2f5', color: '#65676b', fontWeight: 600, marginLeft: 8,
  },
  empty: { textAlign: 'center', padding: 60, color: '#65676b' },
}

const initForm = { name: '', email: '', password: '', headless: true }

export default function Accounts() {
  const [accounts, setAccounts] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState(initForm)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    try {
      const res = await getAccounts()
      setAccounts(res.data)
    } catch { toast.error('Không tải được danh sách tài khoản') }
  }

  useEffect(() => { load() }, [])

  const submit = async (e) => {
    e.preventDefault()
    if (!form.name || !form.email || !form.password) {
      toast.error('Vui lòng điền tên, SĐT/email và mật khẩu')
      return
    }
    setLoading(true)
    try {
      await createAccount(form)
      toast.success('Đã thêm tài khoản!')
      setShowModal(false)
      setForm(initForm)
      load()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Lỗi khi thêm tài khoản')
    } finally { setLoading(false) }
  }

  const remove = async (id, name) => {
    if (!confirm(`Xóa tài khoản "${name}"?`)) return
    try {
      await deleteAccount(id)
      toast.success('Đã xóa tài khoản')
      load()
    } catch { toast.error('Không xóa được tài khoản') }
  }

  return (
    <div style={s.page}>
      <div style={s.header}>
        <h1 style={s.title}>👤 Tài khoản Facebook</h1>
        <button style={{ ...s.btn, ...s.btnPrimary }} onClick={() => setShowModal(true)}>
          + Thêm tài khoản
        </button>
      </div>

      {accounts.length === 0 ? (
        <div style={s.empty}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>👤</div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>Chưa có tài khoản nào</div>
          <div style={{ fontSize: 13, marginTop: 6 }}>Thêm tài khoản Facebook để bắt đầu đăng bài</div>
        </div>
      ) : (
        accounts.map((acc) => (
          <div key={acc.id} style={s.card}>
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <div style={s.avatar}>{acc.name[0]?.toUpperCase()}</div>
              <div style={s.info}>
                <div style={s.name}>
                  {acc.name}
                  {acc.headless !== false ? (
                    <span style={s.badge}>Chạy ngầm</span>
                  ) : (
                    <span style={{ ...s.badge, background: '#fff3cd', color: '#856404' }}>Hiện trình duyệt</span>
                  )}
                </div>
                <div style={s.email}>{acc.email}</div>
              </div>
            </div>
            <button style={{ ...s.btn, ...s.btnDanger }} onClick={() => remove(acc.id, acc.name)}>
              Xóa
            </button>
          </div>
        ))
      )}

      {showModal && (
        <div style={s.modal} onClick={(e) => e.target === e.currentTarget && setShowModal(false)}>
          <div style={s.modalBox}>
            <h2 style={{ marginBottom: 24, fontSize: 20, fontWeight: 700 }}>Thêm tài khoản Facebook</h2>
            <form onSubmit={submit}>
              <div style={s.field}>
                <label style={s.label}>Tên hiển thị</label>
                <input style={s.input} placeholder="VD: Tài khoản chính"
                  value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
              </div>
              <div style={s.field}>
                <label style={s.label}>Số điện thoại / Email đăng nhập</label>
                <input style={s.input} placeholder="038xxxxxxxx hoặc email@gmail.com"
                  value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
                <div style={{ fontSize: 12, color: '#65676b', marginTop: 4 }}>
                  Dùng SĐT hoặc email bạn hay đăng nhập Facebook
                </div>
              </div>
              <div style={s.field}>
                <label style={s.label}>Mật khẩu Facebook</label>
                <input style={s.input} type="password" placeholder="••••••••"
                  value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
              </div>
              <div style={s.radioGroup}>
                <label style={{ ...s.label, marginBottom: 8 }}>Chế độ trình duyệt</label>
                <label style={s.checkRow}>
                  <input
                    type="radio"
                    name="browserMode"
                    checked={form.headless === true}
                    onChange={() => setForm({ ...form, headless: true })}
                  />
                  <div>
                    <div style={{ fontSize: 14 }}>Chạy ngầm</div>
                    <div style={s.radioHint}>Không hiện cửa sổ Chrome — phù hợp đăng tự động</div>
                  </div>
                </label>
                <label style={s.checkRow}>
                  <input
                    type="radio"
                    name="browserMode"
                    checked={form.headless === false}
                    onChange={() => setForm({ ...form, headless: false })}
                  />
                  <div>
                    <div style={{ fontSize: 14 }}>Hiện trình duyệt</div>
                    <div style={s.radioHint}>Mở popup Chrome — xem đăng nhập, xử lý 2FA nếu cần</div>
                  </div>
                </label>
              </div>
              <div style={s.row}>
                <button type="button" style={{ ...s.btn, flex: 1, background: '#f0f2f5', color: '#1c1e21' }}
                  onClick={() => setShowModal(false)}>Hủy</button>
                <button type="submit" style={{ ...s.btn, ...s.btnPrimary, flex: 2 }} disabled={loading}>
                  {loading ? 'Đang lưu...' : 'Thêm tài khoản'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
