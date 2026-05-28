const styles = {
  scroll: { maxHeight: 280, overflowY: 'auto', marginRight: -4, paddingRight: 4 },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  selectAll: { fontSize: 12, color: '#1877f2', cursor: 'pointer', fontWeight: 600, border: 'none', background: 'none', padding: 0 },
  checkItem: { display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid #f0f2f5', cursor: 'pointer' },
  count: { fontSize: 12, color: '#65676b', marginTop: 8 },
}

export default function CheckList({
  title,
  icon,
  items,
  selected,
  onToggle,
  onSelectAll,
  renderItem,
  emptyText,
  maxHeight = 280,
}) {
  const ids = items.map((i) => i.id)
  const allSelected = ids.length > 0 && ids.every((id) => selected.includes(id))

  const handleSelectAll = () => {
    if (allSelected) onSelectAll([])
    else onSelectAll([...ids])
  }

  return (
    <>
      <div style={styles.header}>
        <div style={{ fontSize: 14, fontWeight: 700, color: '#1c1e21' }}>
          {icon && <span style={{ marginRight: 6 }}>{icon}</span>}
          {title}
        </div>
        {items.length > 0 && (
          <button type="button" style={styles.selectAll} onClick={handleSelectAll}>
            {allSelected ? 'Bỏ chọn tất cả' : 'Chọn tất cả'}
          </button>
        )}
      </div>
      {items.length === 0 ? (
        <div style={{ color: '#65676b', fontSize: 13 }}>{emptyText}</div>
      ) : (
        <div style={{ ...styles.scroll, maxHeight }}>
          {items.map((item) => (
            <div
              key={item.id}
              style={styles.checkItem}
              role="button"
              tabIndex={0}
              onClick={() => onToggle(item.id)}
              onKeyDown={(e) => e.key === 'Enter' && onToggle(item.id)}
            >
              <input type="checkbox" readOnly tabIndex={-1} checked={selected.includes(item.id)} />
              {renderItem(item)}
            </div>
          ))}
        </div>
      )}
      <div style={styles.count}>{selected.length} / {items.length} được chọn</div>
    </>
  )
}
