/**
 * API Client - Centralized API communication
 * Handles all REST API calls to the backend
 */

class EmulatorAPI {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
    }

    /**
     * Generic API call handler
     */
    async _call(endpoint, method = 'GET', body = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };

        if (body) {
            options.body = JSON.stringify(body);
        }

        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, options);

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API call failed: ${method} ${endpoint}`, error);
            throw error;
        }
    }

    // ========================================================================
    // System Status
    // ========================================================================

    async getStatus() {
        return this._call('/api/status');
    }

    // ========================================================================
    // Device Management
    // ========================================================================

    async createDevice(name, type, ipAddress = null, subnetMask = '255.255.255.0') {
        return this._call('/api/devices', 'POST', {
            name,
            type,
            ip_address: ipAddress,
            subnet_mask: subnetMask
        });
    }

    async listDevices() {
        return this._call('/api/devices');
    }

    async deleteDevice(deviceName) {
        return this._call(`/api/devices/${deviceName}`, 'DELETE');
    }

    // ========================================================================
    // Link Management
    // ========================================================================

    async createLink(deviceA, deviceB, latencyMs = 0, bandwidthMbps = 1000) {
        return this._call('/api/links', 'POST', {
            device_a: deviceA,
            device_b: deviceB,
            latency_ms: latencyMs,
            bandwidth_mbps: bandwidthMbps
        });
    }

    async listLinks() {
        return this._call('/api/links');
    }

    async deleteLink(linkId) {
        return this._call(`/api/links/${linkId}`, 'DELETE');
    }

    // ========================================================================
    // Failure Injection
    // ========================================================================

    async injectFailure(device, failureType, options = {}) {
        const payload = {
            device,
            failure_type: failureType,
            ...options
        };
        return this._call('/api/failures', 'POST', payload);
    }

    async blockICMP(device) {
        return this.injectFailure(device, 'block_icmp');
    }

    async enableSilentRouter(device) {
        return this.injectFailure(device, 'silent_router');
    }

    async setInterfaceDown(device, interfaceName = 'eth0') {
        return this.injectFailure(device, 'interface_down', {
            interface: interfaceName
        });
    }

    async enablePacketLoss(device, percentage, interfaceName = 'eth0') {
        return this.injectFailure(device, 'packet_loss', {
            interface: interfaceName,
            percentage
        });
    }

    async listFailures() {
        return this._call('/api/failures');
    }

    async removeFailure(device, failureType) {
        return this._call(`/api/failures/${device}/${failureType}`, 'DELETE');
    }

    // ========================================================================
    // Command Execution (Alternative to WebSocket)
    // ========================================================================

    async executeCommand(device, command) {
        return this._call('/api/execute', 'POST', {
            device,
            command
        });
    }

    // ========================================================================
    // WebSocket Connections
    // ========================================================================

    connectTerminal(device) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/terminal/${device}`;
        return new WebSocket(wsUrl);
    }

    connectPacketStream() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/packets`;
        return new WebSocket(wsUrl);
    }

    // ========================================================================
    // Batch Operations
    // ========================================================================

    async createTopology(devices, links) {
        const results = {
            devices: [],
            links: [],
            errors: []
        };

        // Create devices first
        for (const device of devices) {
            try {
                const result = await this.createDevice(
                    device.name,
                    device.type,
                    device.ip_address,
                    device.subnet_mask
                );
                results.devices.push(result);
            } catch (error) {
                results.errors.push({
                    type: 'device',
                    device: device.name,
                    error: error.message
                });
            }
        }

        // Then create links
        for (const link of links) {
            try {
                const result = await this.createLink(
                    link.device_a,
                    link.device_b,
                    link.latency_ms,
                    link.bandwidth_mbps
                );
                results.links.push(result);
            } catch (error) {
                results.errors.push({
                    type: 'link',
                    link: `${link.device_a} <-> ${link.device_b}`,
                    error: error.message
                });
            }
        }

        return results;
    }

    async clearTopology() {
        const devices = await this.listDevices();
        const results = {
            deleted: [],
            errors: []
        };

        for (const device of devices.devices) {
            try {
                await this.deleteDevice(device.name);
                results.deleted.push(device.name);
            } catch (error) {
                results.errors.push({
                    device: device.name,
                    error: error.message
                });
            }
        }

        return results;
    }

    // ========================================================================
    // Utility Methods
    // ========================================================================

    async ping(sourceDevice, targetIp) {
        return this.executeCommand(sourceDevice, `ping -c 4 ${targetIp}`);
    }

    async traceroute(sourceDevice, targetIp) {
        return this.executeCommand(sourceDevice, `traceroute ${targetIp}`);
    }

    async ifconfig(device) {
        return this.executeCommand(device, 'ifconfig');
    }

    async route(device) {
        return this.executeCommand(device, 'route -n');
    }

    async arpTable(device) {
        return this.executeCommand(device, 'arp -n');
    }
}

// Create global API instance
window.api = new EmulatorAPI();

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EmulatorAPI;
}
