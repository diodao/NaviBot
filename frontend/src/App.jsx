import { useState, useEffect } from 'react'
import './App.css'

const API_URL = '/api'

function getToken() { return localStorage.getItem('navibot_token') }
function setToken(t) { localStorage.setItem('navibot_token', t) }
function removeToken() { localStorage.removeItem('navibot_token') }

async function apiFetch(path, options = {}) {
  const token = getToken()
  const headers = { ...options.headers }
  if (!options.isFormData) headers['Content-Type'] = 'application/json'
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${API_URL}${path}`, { ...options, headers })
  const data = await res.json()
  if (res.status === 401) {
    removeToken()
    window.location.reload()
  }
  return { ok: res.ok, status: res.status, data }
}

function avatarUrl(avatar) {
  if (!avatar) return null
  return `${API_URL}/avatars/${avatar}`
}

function UserAvatar({ avatar, name, size = 32 }) {
  const src = avatarUrl(avatar)
  if (src) {
    return <img src={src} alt={name} className="user-avatar" style={{ width: size, height: size }} />
  }
  const initial = (name || '?')[0].toUpperCase()
  return (
    <div className="user-avatar user-avatar-placeholder" style={{ width: size, height: size, fontSize: size * 0.45 }}>
      {initial}
    </div>
  )
}

function CopyButton({ text, label = 'Скопировать' }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button className="btn-copy" onClick={handleCopy}>
      {copied ? 'Скопировано!' : label}
    </button>
  )
}

function formatResult(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*([^*]+)\*/g, '<strong>$1</strong>')
}

const ROLE_LABELS = { admin: 'Админ', editor: 'Редактор', manager: 'Менеджер' }

// === Login Screen ===
function LoginScreen({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    const { ok, data } = await apiFetch('/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    })
    setLoading(false)
    if (ok) {
      setToken(data.token)
      onLogin(data.user)
    } else {
      setError(data.error || 'Ошибка входа')
    }
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <img src="/logo.png" alt="NaviBot" className="login-logo" />
        <h1>NaviBot</h1>
        <p className="subtitle">Расчёт стоимости аренды теплоходов</p>
        <form onSubmit={handleSubmit} className="login-form">
          <input type="text" placeholder="Логин" value={username}
            onChange={e => setUsername(e.target.value)} autoFocus
            autoCapitalize="none" autoCorrect="off" autoComplete="username" />
          <input type="password" placeholder="Пароль" value={password}
            onChange={e => setPassword(e.target.value)} autoComplete="current-password" />
          {error && <div className="login-error">{error}</div>}
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Вхожу...' : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  )
}

// === Boats Management ===
function BoatsPanel() {
  const [boats, setBoats] = useState([])
  const [search, setSearch] = useState('')
  const [editBoat, setEditBoat] = useState(null)
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)

  const loadBoats = async () => {
    const { ok, data } = await apiFetch('/boats')
    if (ok) setBoats(data.boats)
  }

  useEffect(() => { loadBoats() }, [])

  const startEdit = (boat) => {
    setEditBoat(boat)
    setForm({
      link: boat.link || '',
      dock: boat.dock || '',
      cleaning_cost: boat.cleaning_cost || 3000,
      prep_hours: boat.prep_hours || 1,
      unload_hours: boat.unload_hours || 0.5
    })
  }

  const handleSave = async () => {
    setSaving(true)
    await apiFetch(`/boats/${editBoat.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        link: form.link,
        dock: form.dock,
        cleaning_cost: parseFloat(form.cleaning_cost) || 3000,
        prep_hours: parseFloat(form.prep_hours) || 1,
        unload_hours: parseFloat(form.unload_hours) || 0.5
      })
    })
    setSaving(false)
    setEditBoat(null)
    loadBoats()
  }

  const filtered = boats.filter(b =>
    b.name.toLowerCase().includes(search.toLowerCase()) ||
    (b.dock || '').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="boats-panel">
      <div className="boats-header">
        <h3>Теплоходы ({boats.length})</h3>
        <input className="boats-search" placeholder="Поиск по названию или причалу..."
          value={search} onChange={e => setSearch(e.target.value)} />
      </div>

      {editBoat && (
        <div className="boat-edit-form">
          <h4>Редактирование: {editBoat.name}</h4>
          <div className="boat-edit-grid">
            <label>Ссылка
              <input value={form.link} onChange={e => setForm({...form, link: e.target.value})} />
            </label>
            <label>Причал
              <input value={form.dock} onChange={e => setForm({...form, dock: e.target.value})} />
            </label>
            <label>Уборка (₽)
              <input type="number" value={form.cleaning_cost}
                onChange={e => setForm({...form, cleaning_cost: e.target.value})} />
            </label>
            <label>Подготовка (ч)
              <input type="number" step="0.5" value={form.prep_hours}
                onChange={e => setForm({...form, prep_hours: e.target.value})} />
            </label>
            <label>Разгрузка (ч)
              <input type="number" step="0.5" value={form.unload_hours}
                onChange={e => setForm({...form, unload_hours: e.target.value})} />
            </label>
          </div>
          <div className="admin-form-buttons">
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Сохраняю...' : 'Сохранить'}
            </button>
            <button className="btn btn-secondary" onClick={() => setEditBoat(null)}>Отмена</button>
          </div>
        </div>
      )}

      <div className="boats-table-wrapper">
        <table className="admin-table boats-table">
          <thead>
            <tr>
              <th>Название</th>
              <th>Причал</th>
              <th>Уборка</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(b => (
              <tr key={b.id} className={editBoat?.id === b.id ? 'row-editing' : ''}>
                <td className="boat-name-cell">
                  {b.link ? <a href={b.link} target="_blank" rel="noreferrer">{b.name}</a> : b.name}
                </td>
                <td><span className="mobile-label">Причал: </span>{b.dock || '—'}</td>
                <td><span className="mobile-label">Уборка: </span>{b.cleaning_cost ? `${Number(b.cleaning_cost).toLocaleString('ru-RU')}₽` : '—'}</td>
                <td>
                  <button className="btn-small" onClick={() => startEdit(b)}>Изменить</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// === Admin Panel ===
function AdminPanel({ onBack, user }) {
  const [tab, setTab] = useState('users')
  const [users, setUsers] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [editUser, setEditUser] = useState(null)
  const [form, setForm] = useState({ username: '', password: '', display_name: '', role: 'manager' })
  const [error, setError] = useState('')
  const [syncStatus, setSyncStatus] = useState(null)
  const [syncMsg, setSyncMsg] = useState('')

  const loadUsers = async () => {
    const { ok, data } = await apiFetch('/admin/users')
    if (ok) setUsers(data.users)
  }

  const loadSyncStatus = async () => {
    const { ok, data } = await apiFetch('/sync/status')
    if (ok) setSyncStatus(data)
  }

  useEffect(() => { loadUsers(); loadSyncStatus() }, [])

  const resetForm = () => {
    setForm({ username: '', password: '', display_name: '', role: 'manager' })
    setEditUser(null)
    setShowForm(false)
    setError('')
  }

  const handleSave = async () => {
    setError('')
    if (editUser) {
      const body = {}
      if (form.display_name) body.display_name = form.display_name
      if (form.password) body.password = form.password
      if (form.role) body.role = form.role
      const { ok, data } = await apiFetch(`/admin/users/${editUser.id}`, {
        method: 'PUT', body: JSON.stringify(body)
      })
      if (!ok) { setError(data.error); return }
    } else {
      if (!form.username || !form.password || !form.display_name) {
        setError('Заполните все поля'); return
      }
      const { ok, data } = await apiFetch('/admin/users', {
        method: 'POST', body: JSON.stringify(form)
      })
      if (!ok) { setError(data.error); return }
    }
    resetForm()
    loadUsers()
  }

  const handleDelete = async (id) => {
    if (!confirm('Удалить пользователя?')) return
    const { ok, data } = await apiFetch(`/admin/users/${id}`, { method: 'DELETE' })
    if (!ok) { alert(data.error); return }
    loadUsers()
  }

  const startEdit = (u) => {
    setEditUser(u)
    setForm({ username: u.username, password: '', display_name: u.display_name, role: u.role })
    setShowForm(true)
    setError('')
  }

  const handleAvatarUpload = async (userId, file) => {
    const formData = new FormData()
    formData.append('avatar', file)
    const token = getToken()
    const res = await fetch(`${API_URL}/admin/users/${userId}/avatar`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    })
    if (res.ok) loadUsers()
    else alert('Ошибка загрузки')
  }

  const handleAvatarDelete = async (userId) => {
    const { ok } = await apiFetch(`/admin/users/${userId}/avatar`, { method: 'DELETE' })
    if (ok) loadUsers()
  }

  const handleMigrateExcel = async () => {
    setSyncMsg('Мигрирую из Excel...')
    const { ok, data } = await apiFetch('/sync/migrate-excel', { method: 'POST' })
    setSyncMsg(data.message || data.error)
    loadSyncStatus()
    setTimeout(() => setSyncMsg(''), 5000)
  }

  const [syncing, setSyncing] = useState(false)

  const handleSyncWP = async () => {
    setSyncing(true)
    setSyncMsg('Синхронизация с сайтом...')
    const { ok, data } = await apiFetch('/sync/wp', { method: 'POST' })
    setSyncing(false)
    if (ok) {
      let msg = data.message
      if (data.skipped?.length > 0) {
        msg += ` (не найдено в БД: ${data.skipped.length})`
      }
      setSyncMsg(msg)
    } else {
      setSyncMsg(data.error || 'Ошибка синхронизации')
    }
    loadSyncStatus()
    setTimeout(() => setSyncMsg(''), 8000)
  }

  const isAdmin = user.role === 'admin'

  return (
    <div className="admin-panel">
      <div className="admin-header">
        <h2>Панель управления</h2>
        <button className="btn btn-secondary" onClick={onBack}>Назад</button>
      </div>

      <div className="admin-tabs">
        <button className={`admin-tab ${tab === 'users' ? 'active' : ''}`}
          onClick={() => setTab('users')}>Пользователи</button>
        <button className={`admin-tab ${tab === 'boats' ? 'active' : ''}`}
          onClick={() => setTab('boats')}>Теплоходы</button>
        <button className={`admin-tab ${tab === 'sync' ? 'active' : ''}`}
          onClick={() => setTab('sync')}>Синхронизация</button>
      </div>

      {/* === Users Tab === */}
      {tab === 'users' && isAdmin && (
        <>
          <table className="admin-table">
            <thead>
              <tr>
                <th></th>
                <th>Имя</th>
                <th>Логин</th>
                <th>Роль</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id}>
                  <td className="admin-avatar-cell">
                    <div className="admin-avatar-wrapper">
                      <UserAvatar avatar={u.avatar} name={u.display_name} size={36} />
                      <label className="avatar-upload-label">
                        <input type="file" accept="image/png,image/jpeg,image/webp" hidden
                          onChange={e => { if (e.target.files[0]) handleAvatarUpload(u.id, e.target.files[0]); e.target.value = '' }} />
                        <span className="avatar-edit-icon">&#9998;</span>
                      </label>
                      {u.avatar && (
                        <button className="avatar-delete-btn" onClick={() => handleAvatarDelete(u.id)} title="Удалить аватар">&times;</button>
                      )}
                    </div>
                  </td>
                  <td>{u.display_name}</td>
                  <td>{u.username}</td>
                  <td>{ROLE_LABELS[u.role] || u.role}</td>
                  <td className="admin-actions">
                    <button className="btn-small" onClick={() => startEdit(u)}>Изменить</button>
                    <button className="btn-small btn-danger" onClick={() => handleDelete(u.id)}>Удалить</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {!showForm && (
            <button className="btn btn-primary" onClick={() => { resetForm(); setShowForm(true) }}>
              Добавить пользователя
            </button>
          )}

          {showForm && (
            <div className="admin-form">
              <h3>{editUser ? `Редактировать: ${editUser.display_name}` : 'Новый пользователь'}</h3>
              {!editUser && (
                <input placeholder="Логин" value={form.username}
                  onChange={e => setForm({...form, username: e.target.value})} />
              )}
              <input placeholder="Имя" value={form.display_name}
                onChange={e => setForm({...form, display_name: e.target.value})} />
              <input type="password" placeholder={editUser ? 'Новый пароль (оставьте пустым)' : 'Пароль'}
                value={form.password}
                onChange={e => setForm({...form, password: e.target.value})} />
              <select value={form.role} onChange={e => setForm({...form, role: e.target.value})}>
                <option value="manager">Менеджер</option>
                <option value="editor">Редактор</option>
                <option value="admin">Админ</option>
              </select>
              {error && <div className="login-error">{error}</div>}
              <div className="admin-form-buttons">
                <button className="btn btn-primary" onClick={handleSave}>Сохранить</button>
                <button className="btn btn-secondary" onClick={resetForm}>Отмена</button>
              </div>
            </div>
          )}
        </>
      )}

      {/* === Boats Tab === */}
      {tab === 'boats' && <BoatsPanel />}

      {/* === Sync Tab === */}
      {tab === 'sync' && isAdmin && (
        <div className="sync-panel">
          <div className="sync-stats">
            <div className="sync-stat">
              <span className="sync-stat-value">{syncStatus?.boats_count || 0}</span>
              <span className="sync-stat-label">Теплоходов</span>
            </div>
            <div className="sync-stat">
              <span className="sync-stat-value">
                {syncStatus?.last_sync
                  ? new Date(syncStatus.last_sync.created_at + 'Z').toLocaleString('ru-RU')
                  : 'Никогда'}
              </span>
              <span className="sync-stat-label">Последняя синхронизация</span>
            </div>
          </div>

          <div className="sync-actions">
            <button className="btn btn-primary" onClick={handleSyncWP} disabled={syncing}>
              {syncing ? 'Синхронизация...' : 'Синхронизировать с сайтом'}
            </button>
          </div>
          {syncMsg && <div className="update-status">{syncMsg}</div>}
          <p className="sync-hint">
            Синхронизация обновляет цены из teplohod-restoran.ru. Причалы, уборка и ссылки — вручную на вкладке «Теплоходы».
          </p>
        </div>
      )}
    </div>
  )
}

// === Main App ===
function App() {
  const [user, setUser] = useState(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [text, setText] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [history, setHistory] = useState([])
  const [expandedDate, setExpandedDate] = useState(null)
  const [showAdmin, setShowAdmin] = useState(false)
  const [showHint, setShowHint] = useState(() => localStorage.getItem('navibot_hide_hint') !== '1')

  useEffect(() => {
    const token = getToken()
    if (!token) { setAuthChecked(true); return }
    apiFetch('/me').then(({ ok, data }) => {
      if (ok) setUser(data.user)
      else removeToken()
      setAuthChecked(true)
    })
  }, [])

  const loadHistory = async () => {
    const { ok, data } = await apiFetch('/history')
    if (ok) setHistory(data.history)
  }

  useEffect(() => {
    if (user) loadHistory()
  }, [user])

  const handleCalculate = async () => {
    if (!text.trim()) return
    setLoading(true)
    setResults(null)
    const { ok, data } = await apiFetch('/calculate', {
      method: 'POST',
      body: JSON.stringify({ text })
    })
    setLoading(false)
    if (data.error && !data.results) {
      setResults({ error: data.error })
    } else {
      setResults(data)
      loadHistory()
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      e.preventDefault()
      handleCalculate()
    }
  }

  const handleLogout = () => {
    removeToken()
    setUser(null)
    setResults(null)
    setHistory([])
    setShowHistory(false)
    setShowAdmin(false)
  }

  const handleDeleteHistory = async (id) => {
    await apiFetch(`/history/${id}`, { method: 'DELETE' })
    loadHistory()
  }

  // Group history by date
  const groupedHistory = {}
  for (const entry of history) {
    const date = new Date(entry.created_at + 'Z').toLocaleDateString('ru-RU')
    if (!groupedHistory[date]) groupedHistory[date] = []
    groupedHistory[date].push(entry)
  }
  const historyDates = Object.keys(groupedHistory)

  const canAccessAdmin = user && (user.role === 'admin' || user.role === 'editor')

  if (!authChecked) return <div className="loading">Загрузка...</div>
  if (!user) return <LoginScreen onLogin={setUser} />
  if (showAdmin) return (
    <div className="app">
      <header className="header">
        <img src="/logo.png" alt="NaviBot" className="logo" />
        <h1>NaviBot</h1>
      </header>
      <main className="main">
        <AdminPanel onBack={() => setShowAdmin(false)} user={user} />
      </main>
    </div>
  )

  return (
    <div className="app">
      <header className="header">
        <img src="/logo.png" alt="NaviBot" className="logo" />
        <h1>NaviBot</h1>
        <p className="subtitle">Расчёт стоимости аренды теплоходов</p>
        <div className="user-bar">
          <UserAvatar avatar={user.avatar} name={user.display_name} size={28} />
          <span className="user-name">{user.display_name}</span>
          {canAccessAdmin && (
            <button className="btn-small" onClick={() => setShowAdmin(true)}>
              {user.role === 'admin' ? 'Админ' : 'Теплоходы'}
            </button>
          )}
          <button className="btn-small btn-logout" onClick={handleLogout}>Выйти</button>
        </div>
      </header>

      <main className="main">
        <div className="input-section">
          {showHint && (
            <div className="format-hint">
              <button className="hint-close" onClick={() => { setShowHint(false); localStorage.setItem('navibot_hide_hint', '1') }}>&times;</button>
              <strong>Формат запроса:</strong>
              <div className="format-example">
                <code>Дата (dd.mm.yy)</code>
                <code>Название теплохода</code>
                <code>Время (HH:MM-HH:MM или HH:MM-HH:MM-HH:MM-HH:MM)</code>
              </div>
              <p className="hint-note">Можно отправить несколько запросов — по 3 строки на каждый</p>
            </div>
          )}

          <textarea
            className="input-textarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={"16.08.26\nШустрый бобер\n16-17-23-23:30"}
            rows={6}
          />

          <div className="buttons">
            <button className="btn btn-primary" onClick={handleCalculate}
              disabled={loading || !text.trim()}>
              {loading ? 'Рассчитываю...' : 'Рассчитать'}
            </button>
          </div>
          <p className="shortcut-hint">Ctrl+Enter для быстрого расчёта</p>
        </div>

        {results && !results.error && (
          <div className="results-section">
            <div className="results-header">
              <h2>Результаты</h2>
              {results.results?.filter(r => r.result).length > 1 && (
                <CopyButton
                  text={results.results.filter(r => r.result).map(r => r.result).join('\n\n')}
                  label="Скопировать всё"
                />
              )}
            </div>
            {results.results?.map((item, index) => (
              <div key={index} className={`result-card ${item.error ? 'error' : 'success'}`}>
                {item.error ? (
                  <>
                    <div className="result-error">{item.error}</div>
                    {item.input && <div className="result-input">Запрос: {item.input}</div>}
                  </>
                ) : (
                  <>
                    <div className="result-card-header">
                      <CopyButton text={item.result} />
                    </div>
                    <pre className="result-text" dangerouslySetInnerHTML={{ __html: formatResult(item.result) }} />
                  </>
                )}
              </div>
            ))}
          </div>
        )}
        {results?.error && (
          <div className="results-section">
            <h2>Результаты</h2>
            <div className="result-card error">{results.error}</div>
          </div>
        )}

        <div className="history-section">
          <button className="btn btn-history" onClick={() => setShowHistory(!showHistory)}>
            {showHistory ? 'Скрыть историю' : `История расчётов (${history.length})`}
          </button>

          {showHistory && (
            <div className="history-panel">
              {historyDates.length === 0 ? (
                <p className="history-empty">Нет сохранённых расчётов</p>
              ) : (
                historyDates.map(date => (
                  <div key={date} className="history-date-group">
                    <button
                      className={`history-date-btn ${expandedDate === date ? 'active' : ''}`}
                      onClick={() => setExpandedDate(expandedDate === date ? null : date)}
                    >
                      <span>{date}</span>
                      <span className="history-count">{groupedHistory[date].length} расч.</span>
                    </button>
                    {expandedDate === date && (
                      <div className="history-entries">
                        {groupedHistory[date].map(entry => (
                          <div key={entry.id} className="history-entry">
                            <div className="history-entry-header">
                              <span className="history-time">
                                {new Date(entry.created_at + 'Z').toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                              </span>
                              <div className="history-entry-actions">
                                <button className="btn-copy btn-use-query"
                                  onClick={() => { setText(entry.input_text); setShowHistory(false); window.scrollTo(0, 0) }}>
                                  Использовать запрос
                                </button>
                                <button className="btn-copy btn-delete-entry"
                                  onClick={() => handleDeleteHistory(entry.id)}>
                                  Удалить
                                </button>
                              </div>
                            </div>
                            {entry.results?.map((item, i) => (
                              <div key={i} className="history-result">
                                {item.result ? (
                                  <pre className="result-text" dangerouslySetInnerHTML={{ __html: formatResult(item.result) }} />
                                ) : (
                                  <div className="result-error">{item.error}</div>
                                )}
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
