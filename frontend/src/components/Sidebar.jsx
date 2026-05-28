import { NavLink } from 'react-router-dom'

const NAV = [
  { to: '/composer',      icon: '✍️',  label: 'Soạn bài' },
  { to: '/posts-manager', icon: '🗂️',  label: 'Quản lý bài đăng' },
  { to: '/accounts',      icon: '👤',  label: 'Tài khoản FB' },
  { to: '/groups',        icon: '👥',  label: 'Nhóm FB' },
  { to: '/history',       icon: '📋',  label: 'Lịch sử' },
]

const styles = {
  sidebar: {
    width: 220,
    minHeight: '100vh',
    background: 'linear-gradient(180deg, #1877f2 0%, #0d5ec2 100%)',
    color: '#fff',
    display: 'flex',
    flexDirection: 'column',
    padding: '0',
    flexShrink: 0,
    boxShadow: '2px 0 12px rgba(0,0,0,0.15)',
  },
  header: {
    padding: '24px 20px 20px',
    borderBottom: '1px solid rgba(255,255,255,0.2)',
  },
  logo: {
    fontSize: 22,
    fontWeight: 700,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  subtitle: {
    fontSize: 11,
    opacity: 0.75,
    marginTop: 4,
  },
  nav: {
    flex: 1,
    padding: '12px 0',
  },
  link: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '12px 20px',
    color: 'rgba(255,255,255,0.85)',
    textDecoration: 'none',
    fontSize: 14,
    fontWeight: 500,
    transition: 'all 0.15s',
    borderLeft: '3px solid transparent',
  },
  activeLink: {
    background: 'rgba(255,255,255,0.15)',
    color: '#fff',
    borderLeft: '3px solid #fff',
  },
  footer: {
    padding: '16px 20px',
    borderTop: '1px solid rgba(255,255,255,0.2)',
    fontSize: 11,
    opacity: 0.6,
    textAlign: 'center',
  },
}

export default function Sidebar() {
  return (
    <aside style={styles.sidebar}>
      <div style={styles.header}>
        <div style={styles.logo}>
          <span>📘</span>
          <span>FB Auto Poster</span>
        </div>
        <div style={styles.subtitle}>Quản lý đăng bài tự động</div>
      </div>

      <nav style={styles.nav}>
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            style={({ isActive }) => ({
              ...styles.link,
              ...(isActive ? styles.activeLink : {}),
            })}
          >
            <span style={{ fontSize: 18 }}>{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div style={styles.footer}>v1.0.0 · Local Tool</div>
    </aside>
  )
}
