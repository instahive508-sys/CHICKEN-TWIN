"""
CHICKEN TWIN - WebSocket Server
Real-time updates for camera feeds and detection data
"""

import asyncio
import json
import time
import threading
from datetime import datetime

# Try different WebSocket libraries
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

try:
    from flask_socketio import SocketIO, emit
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False


class WebSocketServer:
    """
    WebSocket server for real-time updates
    """
    
    def __init__(self, host='0.0.0.0', port=8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.running = False
        self.server = None
        
        # Channels for different data types
        self.channels = {
            'camera_feed': set(),
            'detections': set(),
            'alerts': set(),
            'robot_status': set(),
            'system_status': set()
        }
        
        # Data queues
        self.broadcast_queue = asyncio.Queue() if WEBSOCKETS_AVAILABLE else None
    
    async def handler(self, websocket, path):
        """Handle WebSocket connections"""
        # Register client
        self.clients.add(websocket)
        client_id = id(websocket)
        print(f"[WebSocket] Client connected: {client_id}")
        
        try:
            # Send welcome message
            await websocket.send(json.dumps({
                'type': 'connected',
                'client_id': client_id,
                'timestamp': datetime.now().isoformat()
            }))
            
            # Handle incoming messages
            async for message in websocket:
                await self._handle_message(websocket, message)
                
        except websockets.exceptions.ConnectionClosed:
            print(f"[WebSocket] Client disconnected: {client_id}")
        finally:
            self.clients.discard(websocket)
            # Remove from all channels
            for channel in self.channels.values():
                channel.discard(websocket)
    
    async def _handle_message(self, websocket, message):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'subscribe':
                # Subscribe to channel
                channel = data.get('channel')
                if channel in self.channels:
                    self.channels[channel].add(websocket)
                    await websocket.send(json.dumps({
                        'type': 'subscribed',
                        'channel': channel
                    }))
            
            elif msg_type == 'unsubscribe':
                # Unsubscribe from channel
                channel = data.get('channel')
                if channel in self.channels:
                    self.channels[channel].discard(websocket)
            
            elif msg_type == 'ping':
                # Respond to ping
                await websocket.send(json.dumps({
                    'type': 'pong',
                    'timestamp': datetime.now().isoformat()
                }))
            
            elif msg_type == 'command':
                # Handle commands (e.g., robot control)
                await self._handle_command(websocket, data)
                
        except json.JSONDecodeError:
            print(f"[WebSocket] Invalid JSON: {message}")
        except Exception as e:
            print(f"[WebSocket] Error handling message: {e}")
    
    async def _handle_command(self, websocket, data):
        """Handle command messages"""
        command = data.get('command')
        payload = data.get('payload', {})
        
        # Process different commands
        if command == 'start_session':
            # Notify session manager to start
            await self.broadcast('system_status', {
                'type': 'session_started',
                'timestamp': datetime.now().isoformat()
            })
        
        elif command == 'stop_session':
            await self.broadcast('system_status', {
                'type': 'session_stopped',
                'timestamp': datetime.now().isoformat()
            })
        
        elif command == 'isolate_bird':
            bird_id = payload.get('bird_id')
            await self.broadcast('robot_status', {
                'type': 'isolation_triggered',
                'bird_id': bird_id,
                'timestamp': datetime.now().isoformat()
            })
    
    async def broadcast(self, channel, data):
        """Broadcast message to all clients in a channel"""
        if channel not in self.channels:
            return
        
        message = json.dumps({
            'channel': channel,
            'data': data,
            'timestamp': datetime.now().isoformat()
        })
        
        # Send to all subscribed clients
        disconnected = set()
        for client in self.channels[channel]:
            try:
                await client.send(message)
            except:
                disconnected.add(client)
        
        # Clean up disconnected clients
        for client in disconnected:
            self.channels[channel].discard(client)
            self.clients.discard(client)
    
    async def broadcast_all(self, data):
        """Broadcast to all connected clients"""
        message = json.dumps(data)
        
        disconnected = set()
        for client in self.clients:
            try:
                await client.send(message)
            except:
                disconnected.add(client)
        
        for client in disconnected:
            self.clients.discard(client)
    
    async def start(self):
        """Start the WebSocket server"""
        if not WEBSOCKETS_AVAILABLE:
            print("[WebSocket] websockets library not available")
            return
        
        self.running = True
        self.server = await websockets.serve(
            self.handler,
            self.host,
            self.port
        )
        
        print(f"[WebSocket] Server started on ws://{self.host}:{self.port}")
        
        # Keep running
        await self.server.wait_closed()
    
    def stop(self):
        """Stop the WebSocket server"""
        self.running = False
        if self.server:
            self.server.close()


class SocketIOServer:
    """
    Alternative WebSocket server using Flask-SocketIO
    Integrates with existing Flask app
    """
    
    def __init__(self, app=None):
        self.socketio = None
        self.clients = {}
        
        if app and SOCKETIO_AVAILABLE:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app"""
        self.socketio = SocketIO(app, cors_allowed_origins="*")
        self._register_handlers()
        return self.socketio
    
    def _register_handlers(self):
        """Register SocketIO event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect():
            from flask import request
            client_id = request.sid
            self.clients[client_id] = {
                'connected_at': datetime.now().isoformat(),
                'subscriptions': []
            }
            print(f"[SocketIO] Client connected: {client_id}")
            emit('connected', {'client_id': client_id})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            from flask import request
            client_id = request.sid
            if client_id in self.clients:
                del self.clients[client_id]
            print(f"[SocketIO] Client disconnected: {client_id}")
        
        @self.socketio.on('subscribe')
        def handle_subscribe(data):
            from flask import request
            channel = data.get('channel')
            client_id = request.sid
            
            if client_id in self.clients:
                if channel not in self.clients[client_id]['subscriptions']:
                    self.clients[client_id]['subscriptions'].append(channel)
                    # Join SocketIO room for this channel
                    from flask_socketio import join_room
                    join_room(channel)
                    emit('subscribed', {'channel': channel})
        
        @self.socketio.on('unsubscribe')
        def handle_unsubscribe(data):
            from flask import request
            channel = data.get('channel')
            client_id = request.sid
            
            if client_id in self.clients:
                if channel in self.clients[client_id]['subscriptions']:
                    self.clients[client_id]['subscriptions'].remove(channel)
                    from flask_socketio import leave_room
                    leave_room(channel)
        
        @self.socketio.on('command')
        def handle_command(data):
            command = data.get('command')
            payload = data.get('payload', {})
            
            # Process command
            result = self._process_command(command, payload)
            emit('command_result', result)
    
    def _process_command(self, command, payload):
        """Process incoming command"""
        return {
            'command': command,
            'status': 'received',
            'timestamp': datetime.now().isoformat()
        }
    
    def broadcast(self, channel, data):
        """Broadcast to a channel"""
        if self.socketio:
            self.socketio.emit(channel, data, room=channel)
    
    def broadcast_all(self, event, data):
        """Broadcast to all clients"""
        if self.socketio:
            self.socketio.emit(event, data)


# ═══════════════════════════════════════════════════════════════
# CLIENT-SIDE WEBSOCKET CODE (Add to frontend)
# ═══════════════════════════════════════════════════════════════

WEBSOCKET_CLIENT_JS = """
// WebSocket Client for CHICKEN TWIN
class ChickenTwinSocket {
    constructor(url = 'ws://localhost:8765') {
        this.url = url;
        this.ws = null;
        this.reconnectInterval = 5000;
        this.handlers = {};
        this.subscriptions = [];
        this.connected = false;
    }
    
    connect() {
        try {
            this.ws = new WebSocket(this.url);
            
            this.ws.onopen = () => {
                console.log('[WebSocket] Connected');
                this.connected = true;
                
                // Resubscribe to channels
                this.subscriptions.forEach(channel => {
                    this.subscribe(channel);
                });
                
                this._trigger('connect');
            };
            
            this.ws.onclose = () => {
                console.log('[WebSocket] Disconnected');
                this.connected = false;
                this._trigger('disconnect');
                
                // Attempt reconnect
                setTimeout(() => this.connect(), this.reconnectInterval);
            };
            
            this.ws.onerror = (error) => {
                console.error('[WebSocket] Error:', error);
                this._trigger('error', error);
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this._handleMessage(data);
                } catch (e) {
                    console.error('[WebSocket] Parse error:', e);
                }
            };
        } catch (error) {
            console.error('[WebSocket] Connection error:', error);
            setTimeout(() => this.connect(), this.reconnectInterval);
        }
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }
    
    subscribe(channel) {
        if (!this.subscriptions.includes(channel)) {
            this.subscriptions.push(channel);
        }
        
        if (this.connected) {
            this.send({
                type: 'subscribe',
                channel: channel
            });
        }
    }
    
    unsubscribe(channel) {
        const idx = this.subscriptions.indexOf(channel);
        if (idx > -1) {
            this.subscriptions.splice(idx, 1);
        }
        
        if (this.connected) {
            this.send({
                type: 'unsubscribe',
                channel: channel
            });
        }
    }
    
    send(data) {
        if (this.connected && this.ws) {
            this.ws.send(JSON.stringify(data));
        }
    }
    
    sendCommand(command, payload = {}) {
        this.send({
            type: 'command',
            command: command,
            payload: payload
        });
    }
    
    on(event, handler) {
        if (!this.handlers[event]) {
            this.handlers[event] = [];
        }
        this.handlers[event].push(handler);
    }
    
    off(event, handler) {
        if (this.handlers[event]) {
            const idx = this.handlers[event].indexOf(handler);
            if (idx > -1) {
                this.handlers[event].splice(idx, 1);
            }
        }
    }
    
    _trigger(event, data) {
        if (this.handlers[event]) {
            this.handlers[event].forEach(handler => handler(data));
        }
    }
    
    _handleMessage(data) {
        // Handle different message types
        if (data.type) {
            this._trigger(data.type, data);
        }
        
        if (data.channel) {
            this._trigger(`channel:${data.channel}`, data.data);
        }
    }
}

// Create global instance
const chickenSocket = new ChickenTwinSocket();

// Usage example:
// chickenSocket.connect();
// chickenSocket.subscribe('detections');
// chickenSocket.on('channel:detections', (data) => {
//     console.log('New detections:', data);
// });
"""


# Utility function to run WebSocket server
def run_websocket_server(host='0.0.0.0', port=8765):
    """Run standalone WebSocket server"""
    if not WEBSOCKETS_AVAILABLE:
        print("websockets library not available. Install with: pip install websockets")
        return
    
    server = WebSocketServer(host, port)
    
    try:
        asyncio.get_event_loop().run_until_complete(server.start())
    except KeyboardInterrupt:
        server.stop()


if __name__ == '__main__':
    run_websocket_server()