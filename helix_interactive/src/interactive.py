"""Interactive Development Mode for Helix CLI"""

import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class ConversationRole(Enum):
    """Conversation participant roles"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class InteractionMode(Enum):
    """Interaction modes"""
    CHAT = "chat"
    DEBUG = "debug"
    REFACTOR = "refactor"
    OPTIMIZE = "optimize"
    LEARN = "learn"
    PAIR_PROGRAM = "pair_program"


@dataclass
class Message:
    """Conversation message"""
    role: ConversationRole
    content: str
    timestamp: str = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ConversationContext:
    """Context for multi-turn conversations"""
    project_path: str
    language: str
    current_file: Optional[str] = None
    selected_code: Optional[str] = None
    error_context: Optional[str] = None
    recent_changes: List[str] = None
    
    def __post_init__(self):
        if self.recent_changes is None:
            self.recent_changes = []


class InteractiveSession:
    """Interactive development session"""
    
    def __init__(self, mode: InteractionMode = InteractionMode.CHAT):
        """Initialize interactive session
        
        Args:
            mode: Interaction mode
        """
        self.mode = mode
        self.conversation_history: List[Message] = []
        self.context: Optional[ConversationContext] = None
        self.session_id = self._generate_session_id()
        self.is_active = False
    
    def start(self, context: ConversationContext) -> str:
        """Start interactive session
        
        Args:
            context: Conversation context
            
        Returns:
            Welcome message
        """
        self.context = context
        self.is_active = True
        
        welcome_msg = self._generate_welcome_message()
        self._add_message(ConversationRole.ASSISTANT, welcome_msg)
        
        return welcome_msg
    
    def send_message(self, user_input: str) -> str:
        """Send message and get response
        
        Args:
            user_input: User message
            
        Returns:
            Assistant response
        """
        if not self.is_active:
            return "Session not active. Start a session first."
        
        # Add user message to history
        self._add_message(ConversationRole.USER, user_input)
        
        # Process message based on mode
        response = self._process_message(user_input)
        
        # Add assistant response to history
        self._add_message(ConversationRole.ASSISTANT, response)
        
        return response
    
    def _process_message(self, user_input: str) -> str:
        """Process user message based on mode"""
        
        if self.mode == InteractionMode.CHAT:
            return self._handle_chat(user_input)
        elif self.mode == InteractionMode.DEBUG:
            return self._handle_debug(user_input)
        elif self.mode == InteractionMode.REFACTOR:
            return self._handle_refactor(user_input)
        elif self.mode == InteractionMode.OPTIMIZE:
            return self._handle_optimize(user_input)
        elif self.mode == InteractionMode.LEARN:
            return self._handle_learn(user_input)
        elif self.mode == InteractionMode.PAIR_PROGRAM:
            return self._handle_pair_program(user_input)
        else:
            return "Unknown mode"
    
    def _handle_chat(self, user_input: str) -> str:
        """Handle chat mode"""
        # Build context for LLM
        system_prompt = f"""You are an expert {self.context.language} developer.
Help the user with coding questions, suggestions, and best practices.
Be concise and practical.
Provide code examples when relevant.
"""
        
        # Call LLM
        response = self._call_llm(system_prompt, user_input)
        
        return response
    
    def _handle_debug(self, user_input: str) -> str:
        """Handle debug mode"""
        system_prompt = """You are an expert debugging assistant.
Help diagnose and fix bugs.
Ask clarifying questions if needed.
Provide step-by-step debugging strategies.
Suggest test cases to verify fixes.
"""
        
        # Include error context if available
        context_msg = ""
        if self.context.error_context:
            context_msg = f"\nError context:\n{self.context.error_context}"
        
        response = self._call_llm(system_prompt, user_input + context_msg)
        
        return response
    
    def _handle_refactor(self, user_input: str) -> str:
        """Handle refactor mode"""
        system_prompt = f"""You are an expert code refactoring specialist in {self.context.language}.
Help refactor code for:
- Readability
- Maintainability
- Performance
- Following best practices

Explain the reasoning behind each change.
"""
        
        # Include selected code if available
        code_msg = ""
        if self.context.selected_code:
            code_msg = f"\nCode to refactor:\n{self.context.selected_code}"
        
        response = self._call_llm(system_prompt, user_input + code_msg)
        
        return response
    
    def _handle_optimize(self, user_input: str) -> str:
        """Handle optimize mode"""
        system_prompt = f"""You are an expert performance optimization specialist in {self.context.language}.
Help optimize code for:
- Speed
- Memory usage
- Resource efficiency

Provide benchmarks and trade-offs.
"""
        
        code_msg = ""
        if self.context.selected_code:
            code_msg = f"\nCode to optimize:\n{self.context.selected_code}"
        
        response = self._call_llm(system_prompt, user_input + code_msg)
        
        return response
    
    def _handle_learn(self, user_input: str) -> str:
        """Handle learn mode"""
        system_prompt = f"""You are an expert {self.context.language} educator.
Teach programming concepts, patterns, and best practices.
Provide clear explanations with examples.
Suggest resources for deeper learning.
"""
        
        response = self._call_llm(system_prompt, user_input)
        
        return response
    
    def _handle_pair_program(self, user_input: str) -> str:
        """Handle pair programming mode"""
        system_prompt = f"""You are an expert pair programming partner in {self.context.language}.
Work collaboratively to solve problems.
Ask questions to understand requirements.
Suggest improvements and alternatives.
Explain your reasoning.
"""
        
        code_msg = ""
        if self.context.selected_code:
            code_msg = f"\nCurrent code:\n{self.context.selected_code}"
        
        response = self._call_llm(system_prompt, user_input + code_msg)
        
        return response
    
    def get_suggestions(self) -> List[str]:
        """Get suggestions based on conversation context"""
        suggestions = []
        
        if self.mode == InteractionMode.DEBUG:
            suggestions = [
                "Add print statements",
                "Use debugger",
                "Check variable values",
                "Review error stack trace",
            ]
        elif self.mode == InteractionMode.REFACTOR:
            suggestions = [
                "Extract function",
                "Rename variables",
                "Remove duplication",
                "Simplify logic",
            ]
        elif self.mode == InteractionMode.OPTIMIZE:
            suggestions = [
                "Profile code",
                "Use caching",
                "Optimize algorithms",
                "Reduce I/O operations",
            ]
        elif self.mode == InteractionMode.LEARN:
            suggestions = [
                "Explain concept",
                "Show examples",
                "Compare approaches",
                "Discuss trade-offs",
            ]
        
        return suggestions
    
    def get_conversation_summary(self) -> str:
        """Get summary of conversation"""
        if not self.conversation_history:
            return "No conversation yet"
        
        summary = f"Session {self.session_id}\n"
        summary += f"Mode: {self.mode.value}\n"
        summary += f"Messages: {len(self.conversation_history)}\n\n"
        
        for msg in self.conversation_history[-5:]:  # Last 5 messages
            summary += f"[{msg.role.value}] {msg.content[:100]}...\n"
        
        return summary
    
    def export_conversation(self, format: str = "json") -> str:
        """Export conversation
        
        Args:
            format: Export format (json, markdown, text)
            
        Returns:
            Exported conversation
        """
        if format == "json":
            return self._export_json()
        elif format == "markdown":
            return self._export_markdown()
        elif format == "text":
            return self._export_text()
        else:
            return "Unknown format"
    
    def _export_json(self) -> str:
        """Export as JSON"""
        data = {
            "session_id": self.session_id,
            "mode": self.mode.value,
            "messages": [
                {
                    "role": msg.role.value,
                    "content": msg.content,
                    "timestamp": msg.timestamp,
                }
                for msg in self.conversation_history
            ]
        }
        return json.dumps(data, indent=2)
    
    def _export_markdown(self) -> str:
        """Export as Markdown"""
        md = f"# Helix Interactive Session\n\n"
        md += f"**Session ID:** {self.session_id}\n"
        md += f"**Mode:** {self.mode.value}\n\n"
        
        for msg in self.conversation_history:
            if msg.role == ConversationRole.USER:
                md += f"## User\n\n{msg.content}\n\n"
            else:
                md += f"## Assistant\n\n{msg.content}\n\n"
        
        return md
    
    def _export_text(self) -> str:
        """Export as plain text"""
        text = f"Helix Interactive Session\n"
        text += f"Session ID: {self.session_id}\n"
        text += f"Mode: {self.mode.value}\n\n"
        
        for msg in self.conversation_history:
            text += f"[{msg.role.value.upper()}]\n{msg.content}\n\n"
        
        return text
    
    def _add_message(self, role: ConversationRole, content: str):
        """Add message to history"""
        msg = Message(role=role, content=content)
        self.conversation_history.append(msg)
    
    def _call_llm(self, system_prompt: str, user_message: str) -> str:
        """Call LLM for response"""
        # This would call the actual LLM API
        # For now, return a mock response
        return f"Response to: {user_message[:50]}...\n\nThis is a mock response from the LLM."
    
    def _generate_welcome_message(self) -> str:
        """Generate welcome message"""
        mode_descriptions = {
            InteractionMode.CHAT: "Chat mode - Ask me anything about coding!",
            InteractionMode.DEBUG: "Debug mode - Let's find and fix bugs together.",
            InteractionMode.REFACTOR: "Refactor mode - Let's improve your code.",
            InteractionMode.OPTIMIZE: "Optimize mode - Let's make your code faster.",
            InteractionMode.LEARN: "Learn mode - Let's explore programming concepts.",
            InteractionMode.PAIR_PROGRAM: "Pair programming mode - Let's code together.",
        }
        
        return f"Welcome to Helix Interactive!\n\n{mode_descriptions[self.mode]}"
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def stop(self) -> str:
        """Stop interactive session"""
        self.is_active = False
        summary = self.get_conversation_summary()
        return f"Session ended.\n\n{summary}"


class InteractiveREPL:
    """Interactive REPL for Helix CLI"""
    
    def __init__(self, mode: InteractionMode = InteractionMode.CHAT):
        """Initialize REPL"""
        self.session = InteractiveSession(mode)
        self.running = False
    
    def run(self, context: ConversationContext):
        """Run interactive REPL"""
        self.running = True
        
        # Start session
        welcome = self.session.start(context)
        print(welcome)
        
        # Main loop
        while self.running:
            try:
                user_input = input("\n> ").strip()
                
                if not user_input:
                    continue
                
                # Handle special commands
                if user_input.lower() == "exit":
                    print(self.session.stop())
                    self.running = False
                elif user_input.lower() == "help":
                    self._show_help()
                elif user_input.lower() == "suggestions":
                    self._show_suggestions()
                elif user_input.lower() == "export":
                    self._export_conversation()
                else:
                    # Send message
                    response = self.session.send_message(user_input)
                    print(f"\nAssistant: {response}")
                    
            except KeyboardInterrupt:
                print("\n\nSession interrupted.")
                self.running = False
            except Exception as e:
                print(f"Error: {e}")
    
    def _show_help(self):
        """Show help"""
        print("""
Available commands:
  exit         - Exit the session
  help         - Show this help
  suggestions  - Get suggestions
  export       - Export conversation
        """)
    
    def _show_suggestions(self):
        """Show suggestions"""
        suggestions = self.session.get_suggestions()
        print("\nSuggestions:")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"  {i}. {suggestion}")
    
    def _export_conversation(self):
        """Export conversation"""
        format_choice = input("Export format (json/markdown/text): ").strip().lower()
        exported = self.session.export_conversation(format_choice)
        
        filename = f"helix_session_{self.session.session_id}.{format_choice}"
        with open(filename, 'w') as f:
            f.write(exported)
        
        print(f"Conversation exported to {filename}")
