import React, { useState } from 'react'
import Toolbar from './components/Toolbar'
import NodePalette from './components/NodePalette'
import NetworkCanvas from './components/NetworkCanvas'
import PropertiesPanel from './components/PropertiesPanel'
import Terminal from './components/Terminal'
import './styles/App.css'

function App() {
  const [selectedTool, setSelectedTool] = useState('select')
  const [selectedNode, setSelectedNode] = useState(null)
  const [selectedLink, setSelectedLink] = useState(null)
  const [terminalOpen, setTerminalOpen] = useState(false)
  const [terminalDevice, setTerminalDevice] = useState(null)

  const handleNodeSelect = (node) => {
    setSelectedNode(node)
    setSelectedLink(null)
  }

  const handleLinkSelect = (link) => {
    setSelectedLink(link)
    setSelectedNode(null)
  }

  const openTerminal = (device) => {
    setTerminalDevice(device)
    setTerminalOpen(true)
  }

  return (
    <div className="app">
      <Toolbar 
        selectedTool={selectedTool} 
        onToolChange={setSelectedTool}
      />
      
      <div className="workspace">
        <NodePalette />
        
        <NetworkCanvas 
          selectedTool={selectedTool}
          onNodeSelect={handleNodeSelect}
          onLinkSelect={handleLinkSelect}
        />
        
        <PropertiesPanel 
          selectedNode={selectedNode}
          selectedLink={selectedLink}
          onOpenTerminal={openTerminal}
        />
      </div>

      {terminalOpen && (
        <Terminal 
          device={terminalDevice}
          onClose={() => setTerminalOpen(false)}
        />
      )}
    </div>
  )
}

export default App
