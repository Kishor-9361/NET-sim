import React, { useEffect, useRef, useState } from 'react'
import useTopology from '../hooks/useTopology'
import usePacketAnimation from '../hooks/usePacketAnimation'
import '../styles/NetworkCanvas.css'

const NetworkCanvas = ({ selectedTool, onNodeSelect, onLinkSelect }) => {
  const canvasRef = useRef(null)
  const [nodes, setNodes] = useState([])
  const [links, setLinks] = useState([])
  const [linkSource, setLinkSource] = useState(null)
  const [hoveredNode, setHoveredNode] = useState(null)
  const [draggedNode, setDraggedNode] = useState(null)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const [scale, setScale] = useState(1)

  const { topology, loading } = useTopology()
  const packets = usePacketAnimation()

  useEffect(() => {
    if (topology) {
      setNodes(topology.devices || [])
      setLinks(topology.links || [])
    }
  }, [topology])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    const render = () => {
      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.save()
      ctx.translate(offset.x, offset.y)
      ctx.scale(scale, scale)

      // Draw links
      links.forEach(link => {
        const source = nodes.find(n => n.name === link.device_a)
        const target = nodes.find(n => n.name === link.device_b)
        if (!source || !target) return

        ctx.beginPath()
        ctx.moveTo(source.x || 400, source.y || 300)
        ctx.lineTo(target.x || 600, target.y || 300)
        ctx.strokeStyle = '#475569'
        ctx.lineWidth = 2
        ctx.stroke()
      })

      // Draw link preview
      if (selectedTool === 'link' && linkSource && hoveredNode) {
        const source = nodes.find(n => n.name === linkSource)
        if (source && hoveredNode !== linkSource) {
          ctx.beginPath()
          ctx.moveTo(source.x || 400, source.y || 300)
          const target = nodes.find(n => n.name === hoveredNode)
          ctx.lineTo(target?.x || 600, target?.y || 300)
          ctx.strokeStyle = '#10b981'
          ctx.lineWidth = 2
          ctx.setLineDash([5, 5])
          ctx.stroke()
          ctx.setLineDash([])
        }
      }

      // Draw nodes
      nodes.forEach(node => {
        const x = node.x || 400
        const y = node.y || 300
        const isSelected = linkSource === node.name
        const isHovered = hoveredNode === node.name

        // Node circle
        ctx.beginPath()
        ctx.arc(x, y, isSelected || isHovered ? 35 : 30, 0, 2 * Math.PI)
        ctx.fillStyle = isSelected ? '#10b981' : '#6366f1'
        ctx.fill()
        if (isSelected || isHovered) {
          ctx.strokeStyle = '#10b981'
          ctx.lineWidth = 3
          ctx.stroke()
        }

        // Node label
        ctx.fillStyle = '#f1f5f9'
        ctx.font = '12px Inter'
        ctx.textAlign = 'center'
        ctx.fillText(node.name, x, y + 50)

        // IP address
        if (node.ip_addresses) {
          const ip = Object.values(node.ip_addresses)[0]
          if (ip) {
            ctx.fillStyle = '#94a3b8'
            ctx.font = '10px Inter'
            ctx.fillText(ip.split('/')[0], x, y + 65)
          }
        }
      })

      // Draw packets
      packets.forEach(packet => {
        const source = nodes.find(n => n.name === packet.source)
        const target = nodes.find(n => n.name === packet.target)
        if (!source || !target) return

        const x = source.x + (target.x - source.x) * packet.progress
        const y = source.y + (target.y - source.y) * packet.progress

        ctx.beginPath()
        ctx.arc(x, y, 5, 0, 2 * Math.PI)
        ctx.fillStyle = packet.type === 'ICMP' ? '#22c55e' : '#3b82f6'
        ctx.fill()
        ctx.strokeStyle = '#fff'
        ctx.lineWidth = 2
        ctx.stroke()
      })

      ctx.restore()
    }

    const animate = () => {
      render()
      requestAnimationFrame(animate)
    }
    animate()
  }, [nodes, links, packets, offset, scale, linkSource, hoveredNode, selectedTool])

  const handleCanvasClick = async (e) => {
    const rect = canvasRef.current.getBoundingClientRect()
    const x = (e.clientX - rect.left - offset.x) / scale
    const y = (e.clientY - rect.top - offset.y) / scale

    // Find clicked node
    const clickedNode = nodes.find(n => {
      const dx = (n.x || 400) - x
      const dy = (n.y || 300) - y
      return Math.sqrt(dx * dx + dy * dy) < 30
    })

    if (selectedTool === 'link') {
      if (clickedNode) {
        if (!linkSource) {
          setLinkSource(clickedNode.name)
        } else if (clickedNode.name !== linkSource) {
          // Create link
          try {
            await fetch('/api/links', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                device_a: linkSource,
                device_b: clickedNode.name,
                latency_ms: 10
              })
            })
            window.dispatchEvent(new Event('topology-updated'))
          } catch (e) {
            console.error('Failed to create link:', e)
          }
          setLinkSource(null)
        }
      }
    } else if (selectedTool === 'select') {
      if (clickedNode) {
        onNodeSelect(clickedNode)
      }
    }
  }

  const handleMouseMove = (e) => {
    const rect = canvasRef.current.getBoundingClientRect()
    const x = (e.clientX - rect.left - offset.x) / scale
    const y = (e.clientY - rect.top - offset.y) / scale

    const hovered = nodes.find(n => {
      const dx = (n.x || 400) - x
      const dy = (n.y || 300) - y
      return Math.sqrt(dx * dx + dy * dy) < 30
    })

    setHoveredNode(hovered?.name || null)

    if (draggedNode && selectedTool === 'select') {
      const node = nodes.find(n => n.name === draggedNode)
      if (node) {
        node.x = x
        node.y = y
        setNodes([...nodes])
      }
    }
  }

  const handleMouseDown = (e) => {
    if (selectedTool !== 'select') return
    const rect = canvasRef.current.getBoundingClientRect()
    const x = (e.clientX - rect.left - offset.x) / scale
    const y = (e.clientY - rect.top - offset.y) / scale

    const node = nodes.find(n => {
      const dx = (n.x || 400) - x
      const dy = (n.y || 300) - y
      return Math.sqrt(dx * dx + dy * dy) < 30
    })

    if (node) setDraggedNode(node.name)
  }

  const handleMouseUp = async () => {
    if (draggedNode) {
      const node = nodes.find(n => n.name === draggedNode)
      if (node) {
        try {
          await fetch(`/api/devices/${draggedNode}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ x: Math.round(node.x), y: Math.round(node.y) })
          })
        } catch (e) {
          console.error('Failed to update node position:', e)
        }
      }
    }
    setDraggedNode(null)
  }

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    canvas.width = canvas.offsetWidth
    canvas.height = canvas.offsetHeight

    const handleResize = () => {
      canvas.width = canvas.offsetWidth
      canvas.height = canvas.offsetHeight
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="network-canvas"
      onClick={handleCanvasClick}
      onMouseMove={handleMouseMove}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
    />
  )
}

export default NetworkCanvas
