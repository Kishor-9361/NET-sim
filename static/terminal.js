/**
 * Terminal Manager - xterm.js Integration
 * Manages real terminal connections to network devices
 */

class TerminalManager {
    constructor() {
        this.terminals = new Map();  // device -> {term, websocket, container}
        this.activeDevice = null;
        this.terminalContainer = document.getElementById('terminal-container');

        if (!this.terminalContainer) {
            console.error('Terminal container not found!');
        }
    }

    /**
     * Create a new terminal for a device
     */
    createTerminal(deviceName) {
        if (this.terminals.has(deviceName)) {
            console.log(`Terminal for ${deviceName} already exists`);
            this.showTerminal(deviceName);
            return;
        }

        console.log(`Creating terminal for ${deviceName}`);

        // Create terminal instance
        const term = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: 'Consolas, "Courier New", monospace',
            theme: {
                background: '#1e1e1e',
                foreground: '#d4d4d4',
                cursor: '#ffffff',
                selection: '#264f78',
                black: '#000000',
                red: '#cd3131',
                green: '#0dbc79',
                yellow: '#e5e510',
                blue: '#2472c8',
                magenta: '#bc3fbc',
                cyan: '#11a8cd',
                white: '#e5e5e5',
                brightBlack: '#666666',
                brightRed: '#f14c4c',
                brightGreen: '#23d18b',
                brightYellow: '#f5f543',
                brightBlue: '#3b8eea',
                brightMagenta: '#d670d6',
                brightCyan: '#29b8db',
                brightWhite: '#ffffff'
            },
            allowTransparency: false,
            scrollback: 1000,
            tabStopWidth: 4
        });

        // Add fit addon for responsive sizing
        const fitAddon = new FitAddon.FitAddon();
        term.loadAddon(fitAddon);

        // Create container for this terminal
        const container = document.createElement('div');
        container.className = 'terminal-instance';
        container.id = `terminal-${deviceName}`;
        container.style.display = 'none';
        container.style.width = '100%';
        container.style.height = '100%';

        this.terminalContainer.appendChild(container);
        term.open(container);
        fitAddon.fit();

        // Connect to WebSocket
        const ws = this.connectWebSocket(deviceName, term, fitAddon);

        // Handle terminal input
        term.onData((data) => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'input',
                    data: data
                }));
            }
        });

        // Store terminal info
        this.terminals.set(deviceName, {
            term,
            websocket: ws,
            container,
            fitAddon
        });

        // Show this terminal
        this.showTerminal(deviceName);

        // Handle window resize
        window.addEventListener('resize', () => {
            if (this.activeDevice === deviceName) {
                this.resizeTerminal(deviceName);
            }
        });

        // Welcome message
        term.writeln('\x1b[1;32m╔════════════════════════════════════════╗\x1b[0m');
        term.writeln('\x1b[1;32m║   Network Emulator Terminal v1.0       ║\x1b[0m');
        term.writeln('\x1b[1;32m╚════════════════════════════════════════╝\x1b[0m');
        term.writeln('');
        term.writeln(`\x1b[1;36mConnected to: ${deviceName}\x1b[0m`);
        term.writeln('\x1b[90mWaiting for shell...\x1b[0m');
        term.writeln('');
    }

    /**
     * Connect WebSocket to backend
     */
    connectWebSocket(deviceName, term, fitAddon) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/terminal/${deviceName}`;

        console.log(`Connecting to WebSocket: ${wsUrl}`);

        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log(`WebSocket connected for ${deviceName}`);
            term.writeln('\x1b[1;32m✓ Connected to device\x1b[0m');
            term.writeln('');

            // Send initial resize
            try {
                fitAddon.fit();
                const dims = fitAddon.proposeDimensions();
                if (dims) {
                    ws.send(JSON.stringify({
                        type: 'resize',
                        rows: dims.rows,
                        cols: dims.cols
                    }));
                }
            } catch (e) {
                console.error("Error sending initial resize:", e);
            }
        };

        ws.onmessage = (event) => {
            // Write PTY output to terminal
            term.write(event.data);
        };

        ws.onerror = (error) => {
            console.error(`WebSocket error for ${deviceName}:`, error);
            term.writeln('\x1b[1;31m✗ Connection error\x1b[0m');
        };

        ws.onclose = () => {
            console.log(`WebSocket closed for ${deviceName}`);
            term.writeln('');
            term.writeln('\x1b[1;33m⚠ Connection closed\x1b[0m');
            term.writeln('\x1b[90mClick to reconnect...\x1b[0m');
        };

        return ws;
    }

    /**
     * Show terminal for a specific device
     */
    showTerminal(deviceName) {
        // Hide all terminals
        this.terminals.forEach((termInfo, name) => {
            termInfo.container.style.display = 'none';
        });

        // Show selected terminal
        const termInfo = this.terminals.get(deviceName);
        if (termInfo) {
            termInfo.container.style.display = 'block';
            this.resizeTerminal(deviceName); // Ensure it's sized correctly
            termInfo.term.focus();
            this.activeDevice = deviceName;

            console.log(`Showing terminal for ${deviceName}`);
        } else {
            console.error(`Terminal for ${deviceName} not found`);
        }
    }

    /**
     * Close terminal for a device
     */
    closeTerminal(deviceName) {
        const termInfo = this.terminals.get(deviceName);
        if (termInfo) {
            // Close WebSocket
            if (termInfo.websocket) {
                termInfo.websocket.close();
            }

            // Dispose terminal
            termInfo.term.dispose();

            // Remove container
            if (termInfo.container && termInfo.container.parentNode) {
                termInfo.container.parentNode.removeChild(termInfo.container);
            }

            // Remove from map
            this.terminals.delete(deviceName);

            console.log(`Closed terminal for ${deviceName}`);

            // If this was the active terminal, show another one
            if (this.activeDevice === deviceName) {
                this.activeDevice = null;
                const remainingDevices = Array.from(this.terminals.keys());
                if (remainingDevices.length > 0) {
                    this.showTerminal(remainingDevices[0]);
                }
            }
        }
    }

    /**
     * Check if terminal exists for device
     */
    hasTerminal(deviceName) {
        return this.terminals.has(deviceName);
    }

    /**
     * Get list of all terminal devices
     */
    getDevices() {
        return Array.from(this.terminals.keys());
    }

    /**
     * Clear terminal screen
     */
    clearTerminal(deviceName) {
        const termInfo = this.terminals.get(deviceName);
        if (termInfo) {
            termInfo.term.clear();
        }
    }

    /**
     * Send command to terminal
     */
    sendCommand(deviceName, command) {
        const termInfo = this.terminals.get(deviceName);
        if (termInfo && termInfo.websocket.readyState === WebSocket.OPEN) {
            termInfo.websocket.send(JSON.stringify({
                type: 'input',
                data: command + '\n'
            }));
        }
    }

    /**
     * Resize terminal
     */
    resizeTerminal(deviceName) {
        const termInfo = this.terminals.get(deviceName);
        if (termInfo) {
            termInfo.fitAddon.fit();
            const dims = termInfo.fitAddon.proposeDimensions();
            if (dims && termInfo.websocket.readyState === WebSocket.OPEN) {
                termInfo.websocket.send(JSON.stringify({
                    type: 'resize',
                    rows: dims.rows,
                    cols: dims.cols
                }));
            }
        }
    }

    /**
     * Cleanup all terminals
     */
    cleanup() {
        this.terminals.forEach((termInfo, deviceName) => {
            this.closeTerminal(deviceName);
        });
    }
}

// Export for use in other scripts
window.TerminalManager = TerminalManager;
