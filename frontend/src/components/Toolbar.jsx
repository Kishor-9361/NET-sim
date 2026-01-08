import React from 'react'
import '../styles/Toolbar.css'

const Toolbar = ({ selectedTool, onToolChange }) => {
  const tools = [
    { id: 'select', icon: 'near_me', label: 'Select' },
    { id: 'link', icon: 'timeline', label: 'Link' },
    { id: 'pan', icon: 'pan_tool', label: 'Pan' }
  ]

  const handleReset = async () => {
    if (!confirm('Reset entire topology?')) return
    try {
      const res = await fetch('/api/devices')
      const data = await res.json()
      for (const device of data.devices) {
        await fetch(`/api/devices/${device.name}`, { method: 'DELETE' })
      }
      window.location.reload()
    } catch (e) {
      console.error('Reset failed:', e)
    }
  }

  return (
    <div className="toolbar">
      <div className="toolbar-left">
        <h1 className="toolbar-title">
          <span className="material-icons-round">hub</span>
          Network Emulator
        </h1>
      </div>

      <div className="toolbar-center">
        {tools.map(tool => (
          <button
            key={tool.id}
            className={`tool-btn ${selectedTool === tool.id ? 'active' : ''}`}
            onClick={() => onToolChange(tool.id)}
            title={tool.label}
          >
            <span className="material-icons-round">{tool.icon}</span>
          </button>
        ))}
      </div>

      <div className="toolbar-right">
        <button className="btn btn-danger" onClick={handleReset}>
          <span className="material-icons-round">refresh</span>
          Reset
        </button>
      </div>
    </div>
  )
}

export default Toolbar
