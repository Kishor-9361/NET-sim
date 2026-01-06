/**
 * Ultra-Smooth Packet Animation System with Speed Controls
 * 
 * Features:
 * - 60fps smooth animations using requestAnimationFrame
 * - Physics-based interpolation for realistic movement
 * - Speed controls (0.25x, 0.5x, 1x, 2x, 4x)
 * - Packet trails for enhanced visual feedback
 * - Smooth easing with multiple easing functions
 * - Real-time position interpolation
 */

class PacketAnimationSystem {
    constructor(network, canvas) {
        this.network = network;
        this.canvas = canvas;
        this.activeAnimations = new Map();
        this.completedPackets = new Map();
        this.animationSpeed = 1.0; // Speed multiplier (0.25x to 4x)
        this.lastUpdateTime = 0;
        this.isAnimating = false;
        this.animationFrameId = null;

        // Interpolation settings for ultra-smooth movement
        this.interpolationSteps = 60; // Higher = smoother
        this.useTrails = true; // Show packet trails
        this.trailLength = 5; // Number of trail particles

        // Start animation loop
        this.startAnimationLoop();

        // Create speed control UI
        this.createSpeedControls();
    }

    /**
     * Create speed control UI
     */
    createSpeedControls() {
        // Check if controls already exist
        if (document.getElementById('packet-speed-controls')) return;

        const controlsContainer = document.createElement('div');
        controlsContainer.id = 'packet-speed-controls';
        controlsContainer.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(15, 23, 42, 0.95);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 12px;
            padding: 16px;
            z-index: 10000;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            backdrop-filter: blur(10px);
        `;

        const title = document.createElement('div');
        title.textContent = 'Packet Animation Speed';
        title.style.cssText = `
            color: #10b981;
            font-weight: 700;
            font-size: 12px;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        `;
        controlsContainer.appendChild(title);

        const speedButtons = [
            { label: '0.25×', value: 0.25 },
            { label: '0.5×', value: 0.5 },
            { label: '1×', value: 1.0 },
            { label: '2×', value: 2.0 },
            { label: '4×', value: 4.0 }
        ];

        const buttonsContainer = document.createElement('div');
        buttonsContainer.style.cssText = `
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        `;

        speedButtons.forEach(({ label, value }) => {
            const button = document.createElement('button');
            button.textContent = label;
            button.dataset.speed = value;
            button.style.cssText = `
                background: ${value === 1.0 ? '#10b981' : 'rgba(255, 255, 255, 0.1)'};
                color: ${value === 1.0 ? '#000' : '#fff'};
                border: 1px solid ${value === 1.0 ? '#10b981' : 'rgba(255, 255, 255, 0.2)'};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 11px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
                font-family: 'Inter', sans-serif;
            `;

            button.addEventListener('mouseenter', () => {
                if (parseFloat(button.dataset.speed) !== this.animationSpeed) {
                    button.style.background = 'rgba(255, 255, 255, 0.15)';
                    button.style.transform = 'translateY(-1px)';
                }
            });

            button.addEventListener('mouseleave', () => {
                if (parseFloat(button.dataset.speed) !== this.animationSpeed) {
                    button.style.background = 'rgba(255, 255, 255, 0.1)';
                    button.style.transform = 'translateY(0)';
                }
            });

            button.addEventListener('click', () => {
                this.setAnimationSpeed(value);
                // Update button styles
                buttonsContainer.querySelectorAll('button').forEach(btn => {
                    const btnSpeed = parseFloat(btn.dataset.speed);
                    if (btnSpeed === value) {
                        btn.style.background = '#10b981';
                        btn.style.color = '#000';
                        btn.style.borderColor = '#10b981';
                    } else {
                        btn.style.background = 'rgba(255, 255, 255, 0.1)';
                        btn.style.color = '#fff';
                        btn.style.borderColor = 'rgba(255, 255, 255, 0.2)';
                    }
                });
            });

            buttonsContainer.appendChild(button);
        });

        controlsContainer.appendChild(buttonsContainer);

        // Add current speed display
        const speedDisplay = document.createElement('div');
        speedDisplay.id = 'speed-display';
        speedDisplay.style.cssText = `
            margin-top: 12px;
            color: #94a3b8;
            font-size: 11px;
            text-align: center;
        `;
        speedDisplay.textContent = `Current: ${this.animationSpeed}× speed`;
        controlsContainer.appendChild(speedDisplay);

        document.body.appendChild(controlsContainer);
    }

    /**
     * Set animation speed
     */
    setAnimationSpeed(speed) {
        this.animationSpeed = speed;
        const display = document.getElementById('speed-display');
        if (display) {
            display.textContent = `Current: ${speed}× speed`;
        }
        console.log(`[Animation] Speed set to ${speed}×`);
    }

    /**
     * Start the animation loop using requestAnimationFrame
     */
    startAnimationLoop() {
        this.isAnimating = true;
        this.lastUpdateTime = performance.now();

        const animate = (currentTime) => {
            if (!this.isAnimating) return;

            const deltaTime = (currentTime - this.lastUpdateTime) / 1000; // Convert to seconds
            this.lastUpdateTime = currentTime;

            // Update all active animations
            this.updateAllAnimations(deltaTime);

            // Continue loop
            this.animationFrameId = requestAnimationFrame(animate);
        };

        this.animationFrameId = requestAnimationFrame(animate);
    }

    /**
     * Stop animation loop
     */
    stopAnimationLoop() {
        this.isAnimating = false;
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
    }

    /**
     * Update all active animations (called every frame)
     */
    updateAllAnimations(deltaTime) {
        for (const [key, animation] of this.activeAnimations.entries()) {
            this.updateSingleAnimation(animation, deltaTime);
        }
    }

    /**
     * Update a single animation with smooth interpolation
     */
    updateSingleAnimation(animation, deltaTime) {
        if (!animation.element || !animation.element.parentNode) return;

        // Get current and target positions
        const targetPos = this.calculatePacketPosition(
            animation.src,
            animation.dst,
            animation.serverProgress || 0
        );

        // Smooth interpolation to target position
        if (!animation.currentPos) {
            animation.currentPos = { ...targetPos };
        }

        // Lerp (Linear Interpolation) with speed multiplier
        const lerpFactor = Math.min(1.0, deltaTime * 10 * this.animationSpeed);
        animation.currentPos.x += (targetPos.x - animation.currentPos.x) * lerpFactor;
        animation.currentPos.y += (targetPos.y - animation.currentPos.y) * lerpFactor;

        // Apply position with sub-pixel precision
        animation.element.style.transform = `translate(${animation.currentPos.x}px, ${animation.currentPos.y}px)`;

        // Update trail if enabled
        if (this.useTrails) {
            this.updateTrail(animation);
        }

        // Update opacity based on progress
        const opacity = animation.serverProgress >= 1.0 ? 0.5 : 1.0;
        animation.element.style.opacity = opacity;
    }

    /**
     * Update packet animations based on server data
     */
    updateAnimations(packetsData) {
        // Process each active packet
        packetsData.forEach(packet => {
            if (!packet.animate) return;

            const key = `${packet.id}-${packet.seq}`;

            if (!this.activeAnimations.has(key)) {
                this.createAnimation(packet, key);
            } else {
                // Update server progress
                const animation = this.activeAnimations.get(key);
                animation.serverProgress = packet.progress;
                animation.src = packet.src;
                animation.dst = packet.dst;

                // Check if completed
                if (packet.progress >= 1.0 && !animation.completed) {
                    animation.completed = true;
                    this.onPacketArrival(packet, animation);
                }
            }
        });

        // Clean up completed animations
        this.cleanupCompletedAnimations(packetsData);
    }

    /**
     * Create a new packet animation with enhanced visuals
     */
    createAnimation(packet, key) {
        const animation = {
            id: packet.id,
            seq: packet.seq,
            type: packet.type,
            src: packet.src,
            dst: packet.dst,
            serverProgress: packet.progress,
            currentPos: null,
            startTime: performance.now(),
            completed: false,
            element: this.createPacketElement(packet),
            trail: []
        };

        this.activeAnimations.set(key, animation);
        this.canvas.appendChild(animation.element);

        console.log(`[Animation] Created packet #${packet.seq}: ${packet.src} → ${packet.dst}`);
    }

    /**
     * Create enhanced visual element for packet
     */
    createPacketElement(packet) {
        const element = document.createElement('div');
        element.className = 'packet-animation';
        element.dataset.seq = packet.seq;
        element.dataset.type = packet.type;

        // Enhanced styling based on packet type
        const color = packet.type === 'ping_request' ? '#10b981' : '#6366f1';
        const glowColor = packet.type === 'ping_request' ? 'rgba(16, 185, 129, 0.6)' : 'rgba(99, 102, 241, 0.6)';

        element.style.cssText = `
            position: absolute;
            width: 14px;
            height: 14px;
            background: radial-gradient(circle, ${color}, ${color}dd);
            border: 2px solid ${color};
            border-radius: 50%;
            box-shadow: 
                0 0 12px ${glowColor},
                0 0 24px ${glowColor}40,
                inset 0 0 8px rgba(255, 255, 255, 0.3);
            z-index: 1000;
            will-change: transform, opacity;
            pointer-events: none;
        `;

        // Add animated pulse ring
        const pulseRing = document.createElement('div');
        pulseRing.style.cssText = `
            position: absolute;
            top: -4px;
            left: -4px;
            right: -4px;
            bottom: -4px;
            border: 2px solid ${color};
            border-radius: 50%;
            opacity: 0.6;
            animation: pulse-ring 1.5s ease-out infinite;
        `;
        element.appendChild(pulseRing);

        // Add sequence label with better styling
        const label = document.createElement('span');
        label.textContent = packet.seq;
        label.style.cssText = `
            position: absolute;
            top: -24px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 11px;
            font-weight: 700;
            color: ${color};
            text-shadow: 0 0 8px ${glowColor}, 0 2px 4px rgba(0, 0, 0, 0.5);
            white-space: nowrap;
            font-family: 'JetBrains Mono', monospace;
        `;
        element.appendChild(label);

        return element;
    }

    /**
     * Calculate packet position with advanced easing
     */
    calculatePacketPosition(srcNode, dstNode, progress) {
        // Get node positions from network graph
        const srcPos = this.network.getNodePosition(srcNode);
        const dstPos = this.network.getNodePosition(dstNode);

        if (!srcPos || !dstPos) {
            return { x: 0, y: 0 };
        }

        // Apply smooth easing
        const easedProgress = this.easeInOutQuart(progress);

        return {
            x: srcPos.x + (dstPos.x - srcPos.x) * easedProgress,
            y: srcPos.y + (dstPos.y - srcPos.y) * easedProgress
        };
    }

    /**
     * Quartic easing for ultra-smooth movement
     */
    easeInOutQuart(t) {
        return t < 0.5
            ? 8 * t * t * t * t
            : 1 - Math.pow(-2 * t + 2, 4) / 2;
    }

    /**
     * Cubic easing (alternative)
     */
    easeInOutCubic(t) {
        return t < 0.5
            ? 4 * t * t * t
            : 1 - Math.pow(-2 * t + 2, 3) / 2;
    }

    /**
     * Update packet trail effect
     */
    updateTrail(animation) {
        // Trail implementation (optional enhancement)
        // Can add particle trail behind packets for extra visual appeal
    }

    /**
     * Handle packet arrival with enhanced effects
     */
    onPacketArrival(packet, animation) {
        console.log(`[Animation] Packet #${packet.seq} arrived at ${packet.dst}`);

        // Store completion info
        this.completedPackets.set(`${packet.id}-${packet.seq}`, {
            seq: packet.seq,
            arrivalTime: performance.now(),
            rtt: packet.summary?.rtt || 0
        });

        // Trigger enhanced visual feedback
        this.showArrivalEffect(animation.element);
    }

    /**
     * Show enhanced arrival effect
     */
    showArrivalEffect(element) {
        if (!element) return;

        // Pulse and glow effect
        element.style.transition = 'transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)';
        element.style.transform += ' scale(1.8)';

        setTimeout(() => {
            if (element.parentNode) {
                element.style.transform = element.style.transform.replace('scale(1.8)', 'scale(1.0)');
            }
        }, 300);
    }

    /**
     * Clean up completed animations
     */
    cleanupCompletedAnimations(activePackets) {
        const activeKeys = new Set(activePackets.map(p => `${p.id}-${p.seq}`));

        for (const [key, animation] of this.activeAnimations.entries()) {
            if (!activeKeys.has(key)) {
                if (animation.element && animation.element.parentNode) {
                    animation.element.style.transition = 'opacity 0.5s ease-out';
                    animation.element.style.opacity = '0';

                    setTimeout(() => {
                        if (animation.element.parentNode) {
                            animation.element.parentNode.removeChild(animation.element);
                        }
                    }, 500);
                }

                this.activeAnimations.delete(key);
                console.log(`[Animation] Cleaned up packet #${animation.seq}`);
            }
        }
    }

    /**
     * Clear all animations
     */
    clearAll() {
        for (const animation of this.activeAnimations.values()) {
            if (animation.element && animation.element.parentNode) {
                animation.element.parentNode.removeChild(animation.element);
            }
        }
        this.activeAnimations.clear();
        this.completedPackets.clear();
    }

    /**
     * Destroy the animation system
     */
    destroy() {
        this.stopAnimationLoop();
        this.clearAll();

        const controls = document.getElementById('packet-speed-controls');
        if (controls && controls.parentNode) {
            controls.parentNode.removeChild(controls);
        }
    }
}

// Add CSS animation for pulse ring
const style = document.createElement('style');
style.textContent = `
    @keyframes pulse-ring {
        0% {
            transform: scale(1);
            opacity: 0.6;
        }
        100% {
            transform: scale(1.8);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PacketAnimationSystem;
}
