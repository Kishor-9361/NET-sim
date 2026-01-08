import React from 'react'
import '../styles/NodePalette.css'

const NodePalette = () => {
  const nodeTypes = [
    { type: 'host', icon: 'computer', label: 'Host' },
    { type: 'router', icon: 'router', label: 'Router' },
    { type: 'switch', icon: 'hub', label: 'Switch' },
    { type: 'dns_server', icon: 'dns', label: 'DNS' }
  ]

  const topologyTypes = [
    { type: 'star', icon: 'hub', label: 'Star Topology' },
    { type: 'mesh', icon: 'share', label: 'Mesh Topology' },
    { type: 'ring', icon: 'sync', label: 'Ring Topology' },
    { type: 'bus', icon: 'linear_scale', label: 'Bus Topology' }
  ]

  const addNode = async (type) => {
    const name = prompt(`Enter ${type} name:`)
    if (!name) return

    try {
      await fetch('/api/devices', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, device_type: type })
      })
      window.dispatchEvent(new Event('topology-updated'))
    } catch (e) {
      console.error('Failed to add node:', e)
    }
  }

  const createTopology = async (type) => {
    const count = prompt(`Enter number of devices for ${type} topology:`)
    if (!count || isNaN(count)) return

    try {
      await fetch('/api/topologies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, device_count: parseInt(count) })
      })
      window.dispatchEvent(new Event('topology-updated'))
    } catch (e) {
      console.error('Failed to create topology:', e)
    }
  }

  return (
    <div className="node-palette">
      {nodeTypes.map(node => (
        <button
          key={node.type}
          className="palette-item"
          onClick={() => addNode(node.type)}
          title={`Add ${node.label}`}
        >
          <span className="material-icons-round">{node.icon}</span>
        </button>
      ))}

      <div style={{ height: '1px', background: 'var(--border)', margin: '4px 2px' }} />

      {topologyTypes.map(topo => (
        <button
          key={topo.type}
          className="palette-item"
          onClick={() => createTopology(topo.type)}
          title={`Create ${topo.label}`}
        >
          <span className="material-icons-round">{topo.icon}</span>
        </button>
      ))}
    </div>
  )
}

export default NodePalette
