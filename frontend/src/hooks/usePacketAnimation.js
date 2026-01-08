import { useState, useEffect } from 'react'

const usePacketAnimation = () => {
  const [packets, setPackets] = useState([])

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/packets')
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'packet') {
        const packet = {
          id: Date.now() + Math.random(),
          source: data.source,
          target: data.target,
          type: data.protocol,
          progress: 0
        }
        
        setPackets(prev => [...prev, packet])
        
        // Animate packet
        let progress = 0
        const interval = setInterval(() => {
          progress += 0.02
          if (progress >= 1) {
            clearInterval(interval)
            setPackets(prev => prev.filter(p => p.id !== packet.id))
          } else {
            setPackets(prev => prev.map(p => 
              p.id === packet.id ? { ...p, progress } : p
            ))
          }
        }, 16)
      }
    }

    return () => ws.close()
  }, [])

  return packets
}

export default usePacketAnimation
