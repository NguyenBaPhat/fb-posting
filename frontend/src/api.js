import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000, // 2 min for Playwright posts
})

api.interceptors.request.use((config) => {
  const method = config.method?.toUpperCase()
  if (config.data instanceof FormData) {
    const fields = {}
    config.data.forEach((value, key) => {
      fields[key] = value instanceof File ? `[File: ${value.name}]` : value
    })
    console.log(`[API] → ${method} ${config.url}`, fields)
  } else {
    console.log(`[API] → ${method} ${config.url}`, config.data ?? '')
  }
  return config
})

api.interceptors.response.use(
  (res) => {
    console.log(`[API] ← ${res.status} ${res.config.url}`, res.data)
    return res
  },
  (err) => {
    const status = err.response?.status
    const url = err.config?.url
    const detail = err.response?.data?.detail ?? err.message
    console.error(`[API] ✗ ${status ?? 'ERR'} ${url}`, detail)
    return Promise.reject(err)
  },
)

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
  api.post('/posts/send', formData)
export const getPostJob = (jobId) => api.get(`/posts/jobs/${jobId}`)
export const getHistory = () => api.get('/posts/history')
export const deleteHistory = (id) => api.delete(`/posts/history/${id}`)

// ── Schedules ─────────────────────────────────────────────
export const getSchedules = () => api.get('/schedules/')
export const createSchedule = (formData) => api.post('/schedules/', formData)
export const deleteSchedule = (id) => api.delete(`/schedules/${id}`)

// ── Comments ──────────────────────────────────────────────
export const getCommentTargets = () => api.get('/comments/targets')
export const sendComments = (formData) => api.post('/comments/send', formData)
export const getCommentJob = (jobId) => api.get(`/comments/jobs/${jobId}`)
export const getCommentHistory = () => api.get('/comments/history')

// ── Posts Manager ─────────────────────────────────────────
export const getSavedPosts = () => api.get('/posts-manager/saved-posts')
export const fetchManagedPosts = (formData) => api.post('/posts-manager/fetch', formData)
export const deleteManagedPosts = (formData) => api.post('/posts-manager/delete', formData)
export const getManagerJob = (jobId) => api.get(`/posts-manager/jobs/${jobId}`)

// ── Templates ─────────────────────────────────────────────
export const getTemplates = () => api.get('/templates/')
export const saveTemplate = (formData) => api.post('/templates/', formData)
export const deleteTemplate = (id) => api.delete(`/templates/${id}`)
export const templateImageUrl = (filename) => `/api/templates/image/${filename}`

// ── Browser (iframe proxy) ────────────────────────────────
// Proxy URL is constructed directly in Browser.jsx — no API call needed
