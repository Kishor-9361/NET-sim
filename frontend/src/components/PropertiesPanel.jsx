import React from 'react'
import '../styles/PropertiesPanel.css'

const PropertiesPanel = ({ selectedNode, selectedLink, onOpenTerminal }) => {
  if (!selectedNode && !selectedLink) {
    return (
      <div className="properties-panel">
        <div className="panel-empty">
          <span className="material-icons-round">info</span>
          <p>Select a node or link to view properties</p>
        </div>
      </div>
    )
  }

  if (selectedNode) {
    return (
      <div className="properties-panel">
        <div className="panel-header">
          <h3>{selectedNode.name}</h3>
          <span className="type-badge">{selectedNode.device_type}</span>
        </div>

        <div className="panel-content">
          <div className="property-group">
            <label>Hostname</label>
            <input type="text" value={selectedNode.name} readOnly />
          </div>

          <div className="property-group">
            <label>IP Addresses</label>
            {selectedNode.ip_addresses && Object.entries(selectedNode.ip_addresses).map(([iface, ip]) => (
              <div key={iface} className="ip-entry">
                {iface}: {ip}
              </div>
            ))}
          </div>

          <button 
            className="btn btn-primary"
            onClick={() => onOpenTerminal(selectedNode.name)}
          >
            <span className="material-icons-round">terminal</span>
            Open Terminal
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="properties-panel">
      <div className="panel-header">
        <h3>Link Properties</h3>
      </div>
      <div className="panel-content">
        <div className="property-group">
          <label>Source</label>
          <input type="text" value={selectedLink.device_a} readOnly />
        </div>
        <div className="property-group">
          <label>Target</label>
          <input type="text" value={selectedLink.device_b} readOnly />
        </div>
        <div className="property-group">
          <label>Latency (ms)</label>
          <input type="number" value={selectedLink.latency_ms} />
        </div>
      </div>
    </div>
  )
}

export default PropertiesPanel
