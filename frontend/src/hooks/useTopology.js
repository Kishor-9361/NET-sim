import { useState, useEffect } from 'react'

const useTopology = () => {
  const [topology, setTopology] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchTopology = async () => {
    try {
      const res = await fetch('/api/state')
      const data = await res.json()
      setTopology(data)
      setLoading(false)
    } catch (e) {
      console.error('Failed to fetch topology:', e)
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTopology()
    
    const handleUpdate = () => fetchTopology()
    window.addEventListener('topology-updated', handleUpdate)
    
    const interval = setInterval(fetchTopology, 2000)
    
    return () => {
      window.removeEventListener('topology-updated', handleUpdate)
      clearInterval(interval)
    }
  }, [])

  return { topology, loading, refresh: fetchTopology }
}

export default useTopology
