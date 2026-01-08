"""
PTY Manager - Kernel-Level Network Emulator

This module manages pseudo-terminals (PTY) for executing real Linux commands
in network namespaces.

CRITICAL: All commands execute as real Linux binaries. NO simulation or fake output.
"""

import pty
import os
import select
import subprocess
import threading
import logging
import signal
from typing import Optional, Callable, Dict
from dataclasses import dataclass
from queue import Queue

logger = logging.getLogger(__name__)


@dataclass
class PTYSession:
    """Represents an active PTY session"""
    session_id: str
    namespace: str
    master_fd: int
    slave_fd: int
    pid: int
    output_queue: Queue
    running: bool = True


class PTYManager:
    """
    Manages pseudo-terminals for command execution in network namespaces.
    
    Each PTY session:
    1. Spawns a bash shell in a network namespace
    2. Captures all stdout/stderr byte-by-byte
    3. Preserves ANSI escape codes
    4. Streams output in real-time
    
    NO command parsing, NO fake output, NO simulation.
    """
    
    def __init__(self):
        self.sessions: Dict[str, PTYSession] = {}
        self.output_callbacks: Dict[str, Callable] = {}
    
    def create_session(self, session_id: str, namespace: str,
                      output_callback: Optional[Callable] = None) -> PTYSession:
        """
        Create a new PTY session in a network namespace.
        
        Args:
            session_id: Unique session identifier
            namespace: Network namespace to execute in
            output_callback: Function to call with output data
        
        Returns:
            PTYSession object
        """
        if session_id in self.sessions:
            raise ValueError(f"Session '{session_id}' already exists")
        
        try:
            # Create PTY
            master_fd, slave_fd = pty.openpty()
            
            # Set non-blocking mode
            os.set_blocking(master_fd, False)
            
            # Fork process
            pid = os.fork()
            
            if pid == 0:
                # Child process
                try:
                    # Close master fd in child
                    os.close(master_fd)
                    
                    # Create new session
                    os.setsid()
                    
                    # Set controlling terminal
                    os.dup2(slave_fd, 0)  # stdin
                    os.dup2(slave_fd, 1)  # stdout
                    os.dup2(slave_fd, 2)  # stderr
                    
                    # Close slave fd
                    if slave_fd > 2:
                        os.close(slave_fd)
                    
                    # Set environment variables
                    os.environ['TERM'] = 'xterm-256color'
                    os.environ['HOME'] = '/root'
                    os.environ['PS1'] = f'[{namespace}] \\u@\\h:\\w\\$ '
                    
                    # Execute bash in namespace directly (no sudo needed since server is root)
                    os.execvp('ip', [
                        'ip', 'netns', 'exec', namespace,
                        '/bin/bash', '-i'
                    ])
                    
                except Exception as e:
                    logger.error(f"Child process error: {e}")
                    os._exit(1)
            
            else:
                # Parent process
                os.close(slave_fd)
                
                # Create session object
                output_queue = Queue()
                session = PTYSession(
                    session_id=session_id,
                    namespace=namespace,
                    master_fd=master_fd,
                    slave_fd=slave_fd,
                    pid=pid,
                    output_queue=output_queue,
                    running=True
                )
                
                self.sessions[session_id] = session
                
                if output_callback:
                    self.output_callbacks[session_id] = output_callback
                
                # Start output reader thread
                reader_thread = threading.Thread(
                    target=self._read_output_loop,
                    args=(session,),
                    daemon=True
                )
                reader_thread.start()
                
                logger.info(f"PTY session created: {session_id} in namespace {namespace}")
                return session
                
        except Exception as e:
            logger.error(f"Failed to create PTY session: {e}")
            raise RuntimeError(f"PTY session creation failed: {e}")
    
    def _read_output_loop(self, session: PTYSession):
        """
        Continuously read output from PTY and queue it.
        Runs in a separate thread.
        """
        while session.running:
            try:
                # Use select to wait for data (with timeout)
                readable, _, _ = select.select([session.master_fd], [], [], 0.1)
                
                if readable:
                    # Read available data
                    try:
                        data = os.read(session.master_fd, 4096)
                        
                        if data:
                            # Queue output
                            session.output_queue.put(data)
                            
                            # Call callback if registered
                            if session.session_id in self.output_callbacks:
                                try:
                                    self.output_callbacks[session.session_id](data)
                                except Exception as e:
                                    logger.error(f"Output callback error: {e}")
                        else:
                            # EOF - process terminated
                            logger.info(f"PTY session ended: {session.session_id}")
                            session.running = False
                            break
                            
                    except OSError as e:
                        if e.errno == 5:  # EIO - process terminated
                            logger.info(f"PTY session terminated: {session.session_id}")
                            session.running = False
                            break
                        else:
                            raise
                            
            except Exception as e:
                logger.error(f"Error reading PTY output: {e}")
                session.running = False
                break
    
    def write_input(self, session_id: str, data: str):
        """
        Write input to PTY (send command).
        
        Args:
            session_id: Session identifier
            data: Input data to send
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session '{session_id}' does not exist")
        
        session = self.sessions[session_id]
        
        if not session.running:
            raise RuntimeError(f"Session '{session_id}' is not running")
        
        try:
            # Write to PTY
            os.write(session.master_fd, data.encode('utf-8'))
            logger.debug(f"Wrote to PTY {session_id}: {repr(data)}")
            
        except Exception as e:
            logger.error(f"Failed to write to PTY: {e}")
            raise RuntimeError(f"PTY write failed: {e}")
    
    def execute_command(self, session_id: str, command: str):
        """
        Execute a command in the PTY session.
        
        Args:
            session_id: Session identifier
            command: Command to execute
        """
        # Add newline if not present
        if not command.endswith('\n'):
            command += '\n'
        
        self.write_input(session_id, command)
        logger.info(f"Executed command in {session_id}: {command.strip()}")
    
    def read_output(self, session_id: str, timeout: float = 0.1) -> Optional[bytes]:
        """
        Read available output from PTY.
        
        Args:
            session_id: Session identifier
            timeout: Timeout in seconds
        
        Returns:
            Output data or None if no data available
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session '{session_id}' does not exist")
        
        session = self.sessions[session_id]
        
        try:
            return session.output_queue.get(timeout=timeout)
        except:
            return None
    
    def send_signal(self, session_id: str, sig: int = signal.SIGINT):
        """
        Send signal to PTY process (e.g., Ctrl+C).
        
        Args:
            session_id: Session identifier
            sig: Signal to send (default: SIGINT)
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session '{session_id}' does not exist")
        
        session = self.sessions[session_id]
        
        try:
            os.kill(session.pid, sig)
            logger.info(f"Sent signal {sig} to session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to send signal: {e}")
            raise RuntimeError(f"Signal send failed: {e}")
    
    def resize_terminal(self, session_id: str, rows: int, cols: int):
        """
        Resize the terminal window.
        
        Args:
            session_id: Session identifier
            rows: Number of rows
            cols: Number of columns
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session '{session_id}' does not exist")
        
        session = self.sessions[session_id]
        
        try:
            import fcntl
            import termios
            import struct
            
            # Set window size
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(session.master_fd, termios.TIOCSWINSZ, winsize)
            
            logger.debug(f"Resized terminal {session_id}: {rows}x{cols}")
            
        except Exception as e:
            logger.error(f"Failed to resize terminal: {e}")
    
    def close_session(self, session_id: str):
        """
        Close a PTY session.
        
        Args:
            session_id: Session identifier
        """
        if session_id not in self.sessions:
            logger.warning(f"Session '{session_id}' does not exist")
            return
        
        session = self.sessions[session_id]
        
        try:
            # Mark as not running
            session.running = False
            
            # Close master fd
            try:
                os.close(session.master_fd)
            except:
                pass
            
            # Kill process
            try:
                os.kill(session.pid, signal.SIGTERM)
                os.waitpid(session.pid, 0)
            except:
                pass
            
            # Remove from sessions
            del self.sessions[session_id]
            
            if session_id in self.output_callbacks:
                del self.output_callbacks[session_id]
            
            logger.info(f"PTY session closed: {session_id}")
            
        except Exception as e:
            logger.error(f"Error closing PTY session: {e}")
    
    def is_running(self, session_id: str) -> bool:
        """Check if a session is running"""
        if session_id not in self.sessions:
            return False
        return self.sessions[session_id].running
    
    def has_session(self, session_id: str) -> bool:
        """Check if a session exists"""
        return session_id in self.sessions
    
    def get_session(self, session_id: str) -> PTYSession:
        """Get a session by ID"""
        if session_id not in self.sessions:
            raise ValueError(f"Session '{session_id}' does not exist")
        return self.sessions[session_id]
    
    def list_sessions(self) -> list:
        """List all active sessions"""
        return [
            {
                'session_id': sid,
                'namespace': session.namespace,
                'running': session.running,
                'pid': session.pid
            }
            for sid, session in self.sessions.items()
        ]
    
    def cleanup_all(self):
        """Close all PTY sessions"""
        logger.info("Cleaning up all PTY sessions...")
        for session_id in list(self.sessions.keys()):
            try:
                self.close_session(session_id)
            except Exception as e:
                logger.error(f"Failed to close session {session_id}: {e}")
        logger.info("Cleanup complete")


class PTYExecutor:
    """
    High-level executor for running commands in namespaces.
    Provides a simpler interface for one-off command execution.
    """
    
    @staticmethod
    def execute(namespace: str, command: str, timeout: float = 30.0) -> dict:
        """
        Execute a command in a namespace and return output.
        
        Args:
            namespace: Network namespace
            command: Command to execute
            timeout: Timeout in seconds
        
        Returns:
            Dict with stdout, stderr, return_code
        """
        try:
            result = subprocess.run(
                ['sudo', 'ip', 'netns', 'exec', namespace, 'bash', '-c', command],
                capture_output=True,
                timeout=timeout,
                text=True
            )
            
            return {
                'stdout': result.stdout,
                'stderr': result.stderr,
                'return_code': result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                'stdout': '',
                'stderr': f'Command timed out after {timeout} seconds',
                'return_code': -1
            }
        except Exception as e:
            return {
                'stdout': '',
                'stderr': str(e),
                'return_code': -1
            }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Note: This example requires a namespace to exist
    # Create namespace first: sudo ip netns add test-ns
    
    def output_handler(data: bytes):
        """Callback for PTY output"""
        print(data.decode('utf-8', errors='replace'), end='', flush=True)
    
    manager = PTYManager()
    
    try:
        # Create session
        session = manager.create_session(
            session_id="test-session",
            namespace="test-ns",
            output_callback=output_handler
        )
        
        # Execute command
        manager.execute_command("test-session", "echo 'Hello from namespace!'")
        
        # Wait a bit for output
        import time
        time.sleep(1)
        
        # Execute another command
        manager.execute_command("test-session", "ip addr show")
        time.sleep(1)
        
    finally:
        # Cleanup
        manager.cleanup_all()
