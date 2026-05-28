export function pollJob(fetchJob, jobId, onUpdate, intervalMs = 1000) {
  return new Promise((resolve, reject) => {
    const tick = async () => {
      try {
        const res = await fetchJob(jobId)
        const job = res.data
        onUpdate(job)
        if (job.status === 'completed') {
          resolve(job)
          return
        }
        if (job.status === 'failed') {
          reject(new Error(job.error || 'Tác vụ thất bại'))
          return
        }
        setTimeout(tick, intervalMs)
      } catch (err) {
        reject(err)
      }
    }
    tick()
  })
}
