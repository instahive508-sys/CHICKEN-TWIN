#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║           CHICKEN TWIN - AI Agent Monitor & Controller           ║
║                                                                  ║
║  Real-time monitoring of AI decisions, robot actions, and       ║
║  complete system state with WebSocket broadcasting              ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import threading
import asyncio
from datetime import datetime
from pathlib import Path
from queue import Queue
import random

# Try to import colorama for colored output
try:
    from colorama import init, Fore, Back, Style
    init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    print("Note: Install 'colorama' for colored output: pip install colorama")

# Try to import OpenAI
try:
    from openai import OpenAI
    from dotenv import load_dotenv
    load_dotenv()
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("Note: Install 'openai' and 'python-dotenv' for AI features")

# Try to import WebSocket
try:
    import websockets
    import asyncio
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════
# COLOR HELPERS
# ═══════════════════════════════════════════════════════════════

def color(text, fg=None, bg=None, bold=False):
    if not HAS_COLOR:
        return text
    result = ""
    if bold:
        result += Style.BRIGHT
    if fg:
        result += getattr(Fore, fg.upper(), "")
    if bg:
        result += getattr(Back, bg.upper(), "")
    result += str(text) + Style.RESET_ALL
    return result

def green(text, bold=False): return color(text, "green", bold=bold)
def red(text, bold=False): return color(text, "red", bold=bold)
def yellow(text, bold=False): return color(text, "yellow", bold=bold)
def blue(text, bold=False): return color(text, "blue", bold=bold)
def cyan(text, bold=False): return color(text, "cyan", bold=bold)
def magenta(text, bold=False): return color(text, "magenta", bold=bold)
def white(text, bold=False): return color(text, "white", bold=bold)

# ═══════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════

class Logger:
    def __init__(self):
        self.log_queue = Queue()
        self.log_file = None
        
    def timestamp(self):
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    def log(self, message, category="INFO", level="info"):
        ts = self.timestamp()
        
        colors = {
            "info": blue,
            "success": green,
            "warning": yellow,
            "error": red,
            "ai": magenta,
            "robot": cyan,
            "session": green,
            "websocket": blue,
            "chicken": yellow
        }
        
        color_fn = colors.get(level, white)
        formatted = f"{white(ts)} │ {color_fn(f'[{category}]', bold=True):15} │ {message}"
        print(formatted)
        
        # Queue for WebSocket broadcast
        self.log_queue.put({
            "timestamp": ts,
            "category": category,
            "message": message,
            "level": level
        })
    
    def divider(self, char="─", length=80):
        print(cyan(char * length))
    
    def section(self, title):
        print()
        self.divider("═")
        print(cyan(f"  {title}  ", bold=True))
        self.divider("═")

logger = Logger()

# ═══════════════════════════════════════════════════════════════
# AI AGENT
# ═══════════════════════════════════════════════════════════════

class AIAgent:
    """
    AI Agent that controls the poultry monitoring system.
    Uses OpenAI for decision making and tool execution.
    """
    
    def __init__(self):
        self.client = None
        self.initialized = False
        self.conversation_history = []
        self.tools_executed = []
        self.current_state = {
            "session_active": False,
            "active_session_id": None,
            "session_start_time": None,
            "chickens": [],
            "quarantine_chickens": [],
            "robot_status": "idle",
            "alerts": [],
            "interventions": 0
        }
        
        # Initialize OpenAI
        if OPENAI_AVAILABLE:
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                self.client = OpenAI(api_key=api_key)
                self.initialized = True
                logger.log("OpenAI client initialized", "AI", "success")
            else:
                logger.log("OPENAI_API_KEY not found in .env", "AI", "warning")
        else:
            logger.log("OpenAI not available - using fallback logic", "AI", "warning")
    
    # Define tools the AI can use
    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "analyze_chicken_health",
                "description": "Analyze a chicken's health based on symptoms and temperature",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chicken_id": {"type": "integer", "description": "The chicken's ID number"},
                        "temperature": {"type": "number", "description": "Body temperature in Celsius"},
                        "symptoms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of observed symptoms"
                        }
                    },
                    "required": ["chicken_id", "temperature"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "dispatch_robot",
                "description": "Send the robot to pick up a chicken for quarantine or treatment",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chicken_id": {"type": "integer", "description": "Target chicken ID"},
                        "action": {
                            "type": "string",
                            "enum": ["pickup", "inject_vaccine", "blood_sample", "examine"],
                            "description": "Action for the robot to perform"
                        },
                        "priority": {"type": "integer", "description": "Priority level 1-10"}
                    },
                    "required": ["chicken_id", "action"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "set_quarantine_temperature",
                "description": "Adjust the quarantine area temperature for optimal recovery",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "temperature": {"type": "number", "description": "Target temperature in Celsius (20-35)"},
                        "reason": {"type": "string", "description": "Reason for temperature change"}
                    },
                    "required": ["temperature"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "generate_alert",
                "description": "Generate an alert for the monitoring system",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "severity": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                            "description": "Alert severity level"
                        },
                        "message": {"type": "string", "description": "Alert message"},
                        "chicken_id": {"type": "integer", "description": "Related chicken ID if applicable"}
                    },
                    "required": ["severity", "message"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_chicken_status",
                "description": "Update a chicken's health status in the system",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chicken_id": {"type": "integer"},
                        "status": {
                            "type": "string",
                            "enum": ["healthy", "warning", "critical", "quarantined", "recovering"]
                        },
                        "diagnosis": {"type": "string", "description": "Health diagnosis"}
                    },
                    "required": ["chicken_id", "status"]
                }
            }
        }
    ]
    
    def execute_tool(self, tool_name, arguments):
        """Execute a tool and return the result"""
        logger.log(f"Executing tool: {tool_name}", "AI-TOOL", "ai")
        logger.log(f"  Arguments: {json.dumps(arguments)}", "AI-TOOL", "info")
        
        self.tools_executed.append({
            "tool": tool_name,
            "arguments": arguments,
            "timestamp": datetime.now().isoformat()
        })
        
        if tool_name == "analyze_chicken_health":
            result = self._analyze_chicken_health(arguments)
        elif tool_name == "dispatch_robot":
            result = self._dispatch_robot(arguments)
        elif tool_name == "set_quarantine_temperature":
            result = self._set_quarantine_temperature(arguments)
        elif tool_name == "generate_alert":
            result = self._generate_alert(arguments)
        elif tool_name == "update_chicken_status":
            result = self._update_chicken_status(arguments)
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
            
        logger.log(f"Tool Execution Complete: {tool_name}", "AI-TOOL", "success")
        logger.log(f"  Result: {json.dumps(result)}", "AI-TOOL", "info")
        return result
    
    def _analyze_chicken_health(self, args):
        chicken_id = args.get("chicken_id")
        temperature = args.get("temperature", 40.0)
        symptoms = args.get("symptoms", [])
        
        # Calculate risk score
        risk = 0.0
        diagnosis = []
        
        # Temperature analysis
        if temperature > 42.5:
            risk += 0.4
            diagnosis.append("High fever detected")
        elif temperature > 41.7:
            risk += 0.2
            diagnosis.append("Elevated temperature")
        elif temperature < 38.0:
            risk += 0.4
            diagnosis.append("Hypothermia detected")
        elif temperature < 39.0:
            risk += 0.2
            diagnosis.append("Low body temperature")
        
        # Symptom analysis
        symptom_weights = {
            "lethargy": 0.2,
            "reduced_movement": 0.15,
            "isolation": 0.15,
            "wing_droop": 0.2,
            "limping": 0.2,
            "ruffled_feathers": 0.1,
            "pale_comb": 0.15,
            "abnormal_feces": 0.25,
            "bloody_feces": 0.4
        }
        
        for symptom in symptoms:
            weight = symptom_weights.get(symptom.lower().replace(" ", "_"), 0.1)
            risk += weight
            diagnosis.append(f"Symptom: {symptom}")
        
        risk = min(1.0, risk)
        
        # Determine action
        if risk >= 0.8:
            action = "immediate_quarantine"
            status = "critical"
        elif risk >= 0.6:
            action = "close_monitoring"
            status = "warning"
        elif risk >= 0.4:
            action = "observation"
            status = "monitoring"
        else:
            action = "none"
            status = "healthy"
        
        result = {
            "chicken_id": chicken_id,
            "risk_score": round(risk, 3),
            "status": status,
            "diagnosis": diagnosis,
            "recommended_action": action,
            "temperature_analysis": f"{temperature}°C - {'Normal' if 40.6 <= temperature <= 41.7 else 'Abnormal'}"
        }
        
        logger.log(f"Health Analysis for Chicken #{chicken_id}:", "AI-ANALYSIS", "ai")
        logger.log(f"  Risk Score: {risk:.2%}", "AI-ANALYSIS", "info")
        logger.log(f"  Status: {status.upper()}", "AI-ANALYSIS", "warning" if status != "healthy" else "success")
        logger.log(f"  Action: {action}", "AI-ANALYSIS", "info")
        
        return result
    
    def _dispatch_robot(self, args):
        chicken_id = args.get("chicken_id")
        action = args.get("action", "pickup")
        priority = args.get("priority", 5)
        
        self.current_state["robot_status"] = f"dispatched_to_{chicken_id}"
        self.current_state["interventions"] += 1
        
        logger.log(f"🤖 ROBOT DISPATCHED", "ROBOT", "robot")
        logger.log(f"  Target: Chicken #{chicken_id}", "ROBOT", "info")
        logger.log(f"  Action: {action.upper()}", "ROBOT", "info")
        logger.log(f"  Priority: {priority}/10", "ROBOT", "info")
        
        # Simulate robot actions
        actions_sequence = []
        
        if action == "pickup":
            actions_sequence = [
                "Moving to chicken position",
                "Extending robotic arm",
                "Gentle capture initiated",
                "Chicken secured in gripper",
                "Transporting to quarantine",
                "Releasing in quarantine zone"
            ]
        elif action == "inject_vaccine":
            actions_sequence = [
                "Moving to chicken position",
                "Extending robotic arm",
                "Gentle capture initiated",
                "Chicken secured",
                "Deploying injection system",
                "Locating wing vein",
                "Administering vaccine",
                "Injection complete",
                "Releasing chicken"
            ]
        elif action == "blood_sample":
            actions_sequence = [
                "Moving to chicken position",
                "Gentle capture initiated",
                "Deploying sampling system",
                "Collecting blood sample",
                "Sample secured",
                "Releasing chicken"
            ]
        
        for step in actions_sequence:
            logger.log(f"  → {step}", "ROBOT", "robot")
        
        return {
            "success": True,
            "chicken_id": chicken_id,
            "action": action,
            "robot_status": "task_complete",
            "actions_performed": actions_sequence
        }
    
    def _set_quarantine_temperature(self, args):
        temperature = args.get("temperature", 28.0)
        reason = args.get("reason", "Standard recovery temperature")
        
        # Clamp temperature
        temperature = max(20, min(35, temperature))
        
        logger.log(f"🌡️ QUARANTINE TEMPERATURE SET", "CLIMATE", "info")
        logger.log(f"  New Temperature: {temperature}°C", "CLIMATE", "success")
        logger.log(f"  Reason: {reason}", "CLIMATE", "info")
        
        return {
            "success": True,
            "temperature": temperature,
            "reason": reason
        }
    
    def _generate_alert(self, args):
        severity = args.get("severity", "medium")
        message = args.get("message", "Alert generated")
        chicken_id = args.get("chicken_id")
        
        alert = {
            "id": f"ALERT_{int(time.time() * 1000)}",
            "severity": severity,
            "message": message,
            "chicken_id": chicken_id,
            "timestamp": datetime.now().isoformat()
        }
        
        self.current_state["alerts"].append(alert)
        
        severity_colors = {
            "low": "info",
            "medium": "warning",
            "high": "error",
            "critical": "error"
        }
        
        logger.log(f"⚠️ ALERT GENERATED [{severity.upper()}]", "ALERT", severity_colors.get(severity, "warning"))
        logger.log(f"  Message: {message}", "ALERT", "info")
        if chicken_id:
            logger.log(f"  Related Bird: #{chicken_id}", "ALERT", "info")
        
        return alert
    
    def _update_chicken_status(self, args):
        chicken_id = args.get("chicken_id")
        status = args.get("status", "healthy")
        diagnosis = args.get("diagnosis", "")
        
        logger.log(f"📋 STATUS UPDATE: Chicken #{chicken_id}", "STATUS", "info")
        logger.log(f"  New Status: {status.upper()}", "STATUS", "success" if status == "healthy" else "warning")
        if diagnosis:
            logger.log(f"  Diagnosis: {diagnosis}", "STATUS", "info")
        
        return {
            "success": True,
            "chicken_id": chicken_id,
            "status": status,
            "diagnosis": diagnosis
        }
    
    def process_chicken_data(self, chicken_data):
        """Process chicken data and make AI decisions"""
        if not self.initialized:
            return self._fallback_process(chicken_data)
        
        try:
            # Build prompt
            prompt = f"""
            Analyze the following chicken health data and decide on appropriate actions.
            
            Chicken ID: #{chicken_data.get('id')}
            Temperature: {chicken_data.get('temperature', 40.0):.1f}°C
            Risk Score: {chicken_data.get('riskScore', 0):.2%}
            Current Status: {chicken_data.get('status', 'unknown')}
            Position: ({chicken_data.get('x', 0):.1f}, {chicken_data.get('z', 0):.1f})
            
            Detected Symptoms: {json.dumps(chicken_data.get('symptoms', []))}
            
            Reference Values:
            - Normal temperature: 40.6°C - 41.7°C
            - Warning: 39°C - 40.6°C or 41.7°C - 42.5°C
            - Critical: Below 39°C or Above 42.5°C
            
            Based on this data, use the available tools to:
            1. Analyze the chicken's health
            2. If necessary, dispatch the robot for intervention
            3. Generate any required alerts
            4. Update the chicken's status
            
            Make decisions based on the severity of symptoms and temperature readings.
            """
            
            messages = [
                {
                    "role": "system",
                    "content": """You are an AI veterinary agent for a poultry health monitoring system.
                    Your role is to analyze chicken health data and make decisions about interventions.
                    Use the provided tools to take appropriate actions.
                    Be decisive but also conservative - only intervene when necessary.
                    Prioritize bird welfare and disease prevention."""
                },
                {"role": "user", "content": prompt}
            ]
            
            logger.log(f"Processing Chicken #{chicken_data.get('id')} with AI...", "AI", "ai")
            
            # Call OpenAI with tools
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                tools=self.TOOLS,
                tool_choice="auto",
                max_tokens=1000
            )
            
            # Process response
            message = response.choices[0].message
            
            if message.tool_calls:
                logger.log(f"AI decided to use {len(message.tool_calls)} tool(s)", "AI", "ai")
                
                tool_results = []
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)
                    
                    result = self.execute_tool(function_name, arguments)
                    tool_results.append({
                        "tool": function_name,
                        "result": result
                    })
                
                return {
                    "success": True,
                    "chicken_id": chicken_data.get('id'),
                    "ai_response": message.content,
                    "tools_used": tool_results
                }
            else:
                logger.log(f"AI Response: {message.content}", "AI", "info")
                return {
                    "success": True,
                    "chicken_id": chicken_data.get('id'),
                    "ai_response": message.content,
                    "tools_used": []
                }
                
        except Exception as e:
            logger.log(f"AI Error: {e}", "AI", "error")
            return self._fallback_process(chicken_data)
    
    def _fallback_process(self, chicken_data):
        """Fallback processing when AI is not available"""
        chicken_id = chicken_data.get('id')
        temp = chicken_data.get('temperature', 40.0)
        risk = chicken_data.get('riskScore', 0)
        
        logger.log(f"Using fallback logic for Chicken #{chicken_id}", "AI-FALLBACK", "warning")
        
        actions = []
        
        if risk >= 0.8 or temp > 42.5 or temp < 38.0:
            actions.append(self._dispatch_robot({"chicken_id": chicken_id, "action": "pickup", "priority": 9}))
            actions.append(self._generate_alert({
                "severity": "critical",
                "message": f"Critical health issue - Chicken #{chicken_id}",
                "chicken_id": chicken_id
            }))
        elif risk >= 0.6:
            actions.append(self._generate_alert({
                "severity": "high",
                "message": f"Elevated risk detected - Chicken #{chicken_id}",
                "chicken_id": chicken_id
            }))
        
        return {
            "success": True,
            "chicken_id": chicken_id,
            "fallback": True,
            "actions": actions
        }

# ═══════════════════════════════════════════════════════════════
# WEBSOCKET SERVER
# ═══════════════════════════════════════════════════════════════

class MonitorWebSocket:
    """WebSocket server for real-time monitoring updates"""
    
    def __init__(self, host='0.0.0.0', port=8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.running = False
        self.ai_agent = AIAgent()
        
    async def handler(self, websocket, path=None):
        """Handle WebSocket connections"""
        self.clients.add(websocket)
        client_id = id(websocket)
        logger.log(f"Client connected: {client_id}", "WEBSOCKET", "websocket")
        
        try:
            await websocket.send(json.dumps({
                "type": "connected",
                "client_id": client_id,
                "timestamp": datetime.now().isoformat()
            }))
            
            # Check for active session and restore
            if self.ai_agent.current_state["session_active"] and self.ai_agent.current_state["active_session_id"]:
                logger.log(f"Restoring session {self.ai_agent.current_state['active_session_id']} for client", "SESSION", "session")
                await websocket.send(json.dumps({
                    "type": "session_restored",
                    "sessionId": self.ai_agent.current_state["active_session_id"],
                    "startTime": self.ai_agent.current_state["session_start_time"],
                    "data": self.ai_agent.current_state
                }))
            
            async for message in websocket:
                await self.process_message(websocket, message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.log(f"Client disconnected: {client_id}", "WEBSOCKET", "info")
        finally:
            self.clients.discard(websocket)
    
    async def process_message(self, websocket, message):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            logger.log(f"Received: {msg_type}", "WEBSOCKET", "websocket")
            
            if msg_type == 'session_start':
                logger.section("SESSION STARTED")
                session_id = data.get('sessionId')
                logger.log(f"Session ID: {session_id}", "SESSION", "session")
                self.ai_agent.current_state["session_active"] = True
                self.ai_agent.current_state["active_session_id"] = session_id
                self.ai_agent.current_state["session_start_time"] = data.get('startTime') or datetime.now().isoformat()
                await self.broadcast({"type": "session_started", "data": data})
                await self.broadcast({"type": "session_active", "data": {"active": True, "sessionId": session_id}})
                
            elif msg_type == 'session_stop':
                logger.section("SESSION STOPPED")
                self.ai_agent.current_state["session_active"] = False
                self.ai_agent.current_state["active_session_id"] = None
                self.ai_agent.current_state["session_start_time"] = None
                await self.broadcast({"type": "session_stopped", "data": data})
                
            elif msg_type == 'chicken_update':
                chickens = data.get('chickens', [])
                quarantine = data.get('quarantine', [])
                robot = data.get('robot', {})
                
                self.ai_agent.current_state["chickens"] = chickens
                self.ai_agent.current_state["quarantine_chickens"] = quarantine
                self.ai_agent.current_state["robot_status"] = robot.get('status', 'idle')
                
                # Process high-risk chickens
                for chicken in chickens:
                    if chicken.get('riskScore', 0) >= 0.7:
                        result = self.ai_agent.process_chicken_data(chicken)
                        await self.broadcast({
                            "type": "ai_decision",
                            "data": result
                        })
                
                # Calculate stats including quarantine
                stats = self.calculate_stats(chickens)
                stats["quarantine"] = len(quarantine)
                stats["robotStatus"] = robot.get('status', 'idle')
                
                await self.broadcast({
                    "type": "stats_update",
                    "data": stats
                })
                
                # Also broadcast robot status
                await self.broadcast({
                    "type": "robot_update",
                    "data": {
                        "status": robot.get('status', 'idle'),
                        "position": f"({robot.get('x', 0):.1f}, {robot.get('z', 0):.1f})" if robot.get('x') else "(0, 0)"
                    }
                })
                
            elif msg_type == 'dashboard_connect':
                # New dashboard connected, send current state
                logger.log("Dashboard connected - sending current state", "WEBSOCKET", "info")
                
                if self.ai_agent.current_state["session_active"]:
                    await websocket.send(json.dumps({
                        "type": "session_active",
                        "data": {
                            "active": True,
                            "sessionId": self.ai_agent.current_state["active_session_id"]
                        }
                    }))
                    
                    # Send current stats
                    chickens = self.ai_agent.current_state.get("chickens", [])
                    quarantine = self.ai_agent.current_state.get("quarantine_chickens", [])
                    stats = self.calculate_stats(chickens)
                    stats["quarantine"] = len(quarantine)
                    
                    await websocket.send(json.dumps({
                        "type": "stats_update",
                        "data": stats
                    }))
                
            elif msg_type == 'alert':
                logger.log(f"Alert: {data.get('message')}", "ALERT", "warning")
                await self.broadcast({"type": "alert", "data": data})
                
            elif msg_type == 'robot_action':
                logger.log(f"Robot: {data.get('action')}", "ROBOT", "robot")
                await self.broadcast({"type": "robot_update", "data": data})
                
            elif msg_type == 'request_ai_analysis':
                chicken_data = data.get('chicken')
                if chicken_data:
                    result = self.ai_agent.process_chicken_data(chicken_data)
                    await websocket.send(json.dumps({
                        "type": "ai_analysis_result",
                        "data": result
                    }))
                    
        except json.JSONDecodeError:
            logger.log(f"Invalid JSON received", "WEBSOCKET", "error")
        except Exception as e:
            logger.log(f"Error processing message: {e}", "WEBSOCKET", "error")
    
    def calculate_stats(self, chickens):
        """Calculate statistics from chicken data"""
        if not chickens:
            return {}
        
        healthy = len([c for c in chickens if c.get('status') == 'healthy'])
        warning = len([c for c in chickens if c.get('status') == 'warning'])
        critical = len([c for c in chickens if c.get('status') in ['critical', 'elevated']])
        
        temps = [c.get('temperature', 40) for c in chickens]
        risks = [c.get('riskScore', 0) for c in chickens]
        
        return {
            "total": len(chickens),
            "healthy": healthy,
            "warning": warning,
            "critical": critical,
            "avgTemp": sum(temps) / len(temps) if temps else 0,
            "avgRisk": sum(risks) / len(risks) if risks else 0,
            "healthScore": (healthy / len(chickens) * 100) if chickens else 0
        }
    
    async def broadcast(self, message):
        """Broadcast message to all connected clients"""
        if not self.clients:
            return
        
        message_json = json.dumps(message)
        disconnected = set()
        
        for client in self.clients:
            try:
                await client.send(message_json)
            except:
                disconnected.add(client)
        
        for client in disconnected:
            self.clients.discard(client)
    
    async def start(self):
        """Start the WebSocket server"""
        if not WEBSOCKET_AVAILABLE:
            logger.log("WebSocket not available - install websockets package", "WEBSOCKET", "error")
            return
        
        self.running = True
        
        # Wrapper to handle both old (with path) and new (without path) websockets API
        async def connection_handler(websocket):
            await self.handler(websocket, path=None)
        
        try:
            server = await websockets.serve(connection_handler, self.host, self.port)
            logger.log(f"WebSocket server started on ws://{self.host}:{self.port}", "WEBSOCKET", "success")
            await server.wait_closed()
        except Exception as e:
            logger.log(f"WebSocket server error: {e}", "WEBSOCKET", "error")
    
    def stop(self):
        self.running = False

# ═══════════════════════════════════════════════════════════════
# SIMULATION MODE
# ═══════════════════════════════════════════════════════════════

def run_simulation():
    """Run a simulation of the monitoring system"""
    logger.section("🎮 SIMULATION MODE")
    
    ai_agent = AIAgent()
    
    # Simulate chickens
    chickens = []
    for i in range(25):
        chicken = {
            "id": i + 1,
            "temperature": 40.6 + random.uniform(-1.5, 2.0),
            "riskScore": random.uniform(0, 0.5),
            "status": "healthy",
            "x": random.uniform(-25, 25),
            "z": random.uniform(-25, 25),
            "symptoms": []
        }
        
        # Make some chickens sick
        if random.random() < 0.15:
            chicken["temperature"] = random.choice([36.5, 37.0, 43.0, 43.5])
            chicken["riskScore"] = random.uniform(0.6, 1.0)
            chicken["status"] = "critical" if chicken["riskScore"] > 0.8 else "warning"
            chicken["symptoms"] = random.sample([
                "lethargy", "wing_droop", "isolation", "reduced_movement", "abnormal_feces"
            ], random.randint(1, 3))
        
        chickens.append(chicken)
    
    logger.log(f"Created {len(chickens)} simulated chickens", "SIM", "info")
    
    # Display table
    logger.section("🐔 FLOCK STATUS")
    
    print()
    print(f"    ┌{'─'*8}┬{'─'*14}┬{'─'*12}┬{'─'*12}┬{'─'*15}┐")
    print(f"    │ {'ID':^6} │ {'Temperature':^12} │ {'Risk':^10} │ {'Status':^10} │ {'Symptoms':^13} │")
    print(f"    ├{'─'*8}┼{'─'*14}┼{'─'*12}┼{'─'*12}┼{'─'*15}┤")
    
    for chicken in chickens[:15]:
        temp = chicken["temperature"]
        risk = chicken["riskScore"]
        status = chicken["status"]
        symptoms = len(chicken["symptoms"])
        
        temp_color = red if (temp > 42.5 or temp < 38) else (yellow if (temp > 41.7 or temp < 39) else green)
        risk_color = red if risk > 0.8 else (yellow if risk > 0.4 else green)
        status_color = red if status == "critical" else (yellow if status == "warning" else green)
        
        print(f"    │ {chicken['id']:^6} │ {temp_color(f'{temp:^12.1f}')} │ {risk_color(f'{risk:^10.2f}')} │ {status_color(f'{status:^10}')} │ {symptoms:^13} │")
    
    if len(chickens) > 15:
        print(f"    │ {'...':^6} │ {'...':^12} │ {'...':^10} │ {'...':^10} │ {'...':^13} │")
    
    print(f"    └{'─'*8}┴{'─'*14}┴{'─'*12}┴{'─'*12}┴{'─'*15}┘")
    
    # Process critical chickens with AI
    critical_chickens = [c for c in chickens if c["status"] in ["critical", "warning"]]
    
    if critical_chickens:
        logger.section("🚨 PROCESSING ALERTS")
        
        for chicken in critical_chickens[:3]:  # Process top 3
            logger.log(f"", "", "")
            logger.divider()
            ai_agent.process_chicken_data(chicken)
            time.sleep(0.5)
    
    # Summary
    logger.section("📊 SESSION SUMMARY")
    
    healthy = len([c for c in chickens if c["status"] == "healthy"])
    warning = len([c for c in chickens if c["status"] == "warning"])
    critical = len([c for c in chickens if c["status"] == "critical"])
    
    print()
    print(f"    ┌{'─'*45}┐")
    print(f"    │ {green('SIMULATION COMPLETE', bold=True):43} │")
    print(f"    ├{'─'*45}┤")
    print(f"    │ Total Birds:     {len(chickens):>24} │")
    print(f"    │ Healthy:         {green(str(healthy)):>24} │")
    print(f"    │ Warning:         {yellow(str(warning)):>24} │")
    print(f"    │ Critical:        {red(str(critical)):>24} │")
    print(f"    │ AI Decisions:    {len(ai_agent.tools_executed):>24} │")
    print(f"    │ Robot Actions:   {ai_agent.current_state['interventions']:>24} │")
    print(f"    └{'─'*45}┘")
    print()

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def print_banner():
    banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║     ██████╗██╗  ██╗██╗ ██████╗██╗  ██╗███████╗███╗   ██╗                     ║
║    ██╔════╝██║  ██║██║██╔════╝██║ ██╔╝██╔════╝████╗  ██║                     ║
║    ██║     ███████║██║██║     █████╔╝ █████╗  ██╔██╗ ██║                     ║
║    ██║     ██╔══██║██║██║     ██╔═██╗ ██╔══╝  ██║╚██╗██║                     ║
║    ╚██████╗██║  ██║██║╚██████╗██║  ██╗███████╗██║ ╚████║                     ║
║     ╚═════╝╚═╝  ╚═╝╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝                     ║
║                                                                              ║
║    ████████╗██╗    ██╗██╗███╗   ██╗                                          ║
║    ╚══██╔══╝██║    ██║██║████╗  ██║                                          ║
║       ██║   ██║ █╗ ██║██║██╔██╗ ██║                                          ║
║       ██║   ██║███╗██║██║██║╚██╗██║                                          ║
║       ██║   ╚███╔███╔╝██║██║ ╚████║                                          ║
║       ╚═╝    ╚══╝╚══╝ ╚═╝╚═╝  ╚═══╝                                          ║
║                                                                              ║
║                    🐔 AI AGENT MONITOR & CONTROLLER 🤖                       ║
║                                                                              ║
║              Surge X Lablab.ai Hackathon Project                             ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
    print(cyan(banner, bold=True))

def show_menu():
    print()
    print(f"    ┌{'─'*50}┐")
    print(f"    │ {cyan('MAIN MENU', bold=True):48} │")
    print(f"    ├{'─'*50}┤")
    print(f"    │ {green('1.')} Run Simulation (Demo Mode)                    │")
    print(f"    │ {green('2.')} Start WebSocket Server                        │")
    print(f"    │ {green('3.')} Test AI Agent                                 │")
    print(f"    │ {green('4.')} System Status Check                           │")
    print(f"    │ {red('0.')} Exit                                          │")
    print(f"    └{'─'*50}┘")
    print()

def test_ai_agent():
    """Test the AI agent with sample data"""
    logger.section("🧪 AI AGENT TEST")
    
    ai_agent = AIAgent()
    
    # Test chicken
    test_chicken = {
        "id": 42,
        "temperature": 43.5,
        "riskScore": 0.85,
        "status": "critical",
        "x": 10.5,
        "z": -5.2,
        "symptoms": ["lethargy", "wing_droop", "abnormal_feces"]
    }
    
    logger.log("Testing with critical chicken data...", "TEST", "info")
    result = ai_agent.process_chicken_data(test_chicken)
    
    logger.log(f"Result: {json.dumps(result, indent=2)}", "TEST", "success")

def system_status_check():
    """Check system status"""
    logger.section("🔧 SYSTEM STATUS")
    
    checks = []
    
    # Python packages
    packages = ['flask', 'flask_cors', 'openai', 'dotenv', 'websockets', 'colorama']
    for pkg in packages:
        try:
            __import__(pkg.replace('-', '_').replace('dotenv', 'dotenv'))
            checks.append((f"Package: {pkg}", True))
        except ImportError:
            checks.append((f"Package: {pkg}", False))
    
    # Files
    files = ['.env', 'server.py', 'demo.html', 'dashboard.html']
    for f in files:
        checks.append((f"File: {f}", Path(f).exists()))
    
    # OpenAI
    api_key = os.getenv('OPENAI_API_KEY')
    checks.append(("OpenAI API Key", bool(api_key)))
    
    # Display
    print()
    print(f"    ┌{'─'*40}┬{'─'*12}┐")
    print(f"    │ {'Component':^38} │ {'Status':^10} │")
    print(f"    ├{'─'*40}┼{'─'*12}┤")
    
    for name, status in checks:
        status_display = green("✓ OK") if status else red("✗ MISSING")
        print(f"    │ {name:38} │ {status_display:^10} │")
    
    print(f"    └{'─'*40}┴{'─'*12}┘")
    
    passed = sum(1 for _, s in checks if s)
    total = len(checks)
    
    print()
    if passed == total:
        logger.log(f"All checks passed! ({passed}/{total})", "STATUS", "success")
    else:
        logger.log(f"Some checks failed: {passed}/{total}", "STATUS", "warning")

async def start_monitoring_server():
    """Start the monitoring websocket server"""
    if not WEBSOCKET_AVAILABLE:
        logger.log("WebSocket not available - install websockets package", "WEBSOCKET", "error")
        return
        
    logger.log("Starting WebSocket server...", "MAIN", "info")
    logger.log("Juggernaut Console Active - Press Ctrl+C to stop", "MAIN", "info")
    
    ws_server = MonitorWebSocket()
    await ws_server.start()

def main():
    print_banner()
    logger.section("🚀 STARTING JUGGERNAUT CONSOLE")
    
    # Run system check automatically
    system_status_check()
    
    # Start loop immediately
    logger.section("📡 STARTING WEBSOCKET SERVER")
    try:
        asyncio.run(start_monitoring_server())
    except KeyboardInterrupt:
        logger.section("🛑 SHUTDOWN")
        logger.log("Shutting down monitor...", "SYSTEM", "warning")
    except Exception as e:
        logger.log(f"Critical Error: {e}", "CRITICAL", "error")

if __name__ == "__main__":
    main()