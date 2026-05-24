import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000, // 2 min for Playwright posts
})

// ── Accounts ──────────────────────────────────────────────
export const getAccounts = () => api.get('/accounts/')
export const createAccount = (data) => api.post('/accounts/', data)
export const updateAccount = (id, data) => api.put(`/accounts/${id}`, data)
export const deleteAccount = (id) => api.delete(`/accounts/${id}`)

// ── Groups ────────────────────────────────────────────────
export const getGroups = () => api.get('/groups/')
export const createGroup = (data) => api.post('/groups/', data)
export const updateGroup = (id, data) => api.put(`/groups/${id}`, data)
export const deleteGroup = (id) => api.delete(`/groups/${id}`)

// ── Posts ─────────────────────────────────────────────────
export const sendPost = (formData) =>
  api.post('/posts/send', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
export const getHistory = () => api.get('/posts/history')
export const deleteHistory = (id) => api.delete(`/posts/history/${id}`)

// ── Schedules ─────────────────────────────────────────────
export const getSchedules = () => api.get('/schedules/')
export const createSchedule = (data) => api.post('/schedules/', data)
export const deleteSchedule = (id) => api.delete(`/schedules/${id}`)
