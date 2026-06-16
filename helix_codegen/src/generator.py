"""AI-Powered Code Generation Module for Helix CLI"""

import json
from typing import Optional, Dict, List
from dataclasses import dataclass
from enum import Enum


class Language(Enum):
    """Supported programming languages"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    CSHARP = "csharp"
    CPP = "cpp"
    SQL = "sql"
    BASH = "bash"


class CodeType(Enum):
    """Types of code to generate"""
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    API_ENDPOINT = "api_endpoint"
    DATABASE_SCHEMA = "database_schema"
    TEST = "test"
    DOCUMENTATION = "documentation"
    CONFIGURATION = "configuration"


@dataclass
class CodeGenerationRequest:
    """Request for code generation"""
    prompt: str
    language: Language
    code_type: CodeType
    context: Optional[str] = None
    style: Optional[str] = None
    include_tests: bool = True
    include_docs: bool = True
    optimization_level: str = "balanced"


@dataclass
class GeneratedCode:
    """Generated code response"""
    code: str
    language: Language
    code_type: CodeType
    tests: Optional[str] = None
    documentation: Optional[str] = None
    explanation: Optional[str] = None
    confidence: float = 0.85
    suggestions: List[str] = None


class CodeGenerator:
    """AI-powered code generator"""
    
    def __init__(self, model: str = "gpt-4", api_key: Optional[str] = None):
        """Initialize code generator
        
        Args:
            model: LLM model to use (gpt-4, claude-3, etc.)
            api_key: API key for the LLM service
        """
        self.model = model
        self.api_key = api_key
        self.cache = {}
        
    def generate(self, request: CodeGenerationRequest) -> GeneratedCode:
        """Generate code from prompt
        
        Args:
            request: Code generation request
            
        Returns:
            Generated code with tests and documentation
        """
        # Build prompt for LLM
        system_prompt = self._build_system_prompt(request)
        user_prompt = self._build_user_prompt(request)
        
        # Generate code using LLM
        code = self._call_llm(system_prompt, user_prompt)
        
        # Extract code, tests, and documentation
        parsed = self._parse_response(code, request)
        
        # Generate tests if requested
        tests = None
        if request.include_tests:
            tests = self._generate_tests(parsed["code"], request)
        
        # Generate documentation if requested
        docs = None
        if request.include_docs:
            docs = self._generate_documentation(parsed["code"], request)
        
        return GeneratedCode(
            code=parsed["code"],
            language=request.language,
            code_type=request.code_type,
            tests=tests,
            documentation=docs,
            explanation=parsed.get("explanation"),
            confidence=parsed.get("confidence", 0.85),
            suggestions=parsed.get("suggestions", [])
        )
    
    def refactor(self, code: str, language: Language, 
                 goal: str = "improve_readability") -> GeneratedCode:
        """Refactor existing code
        
        Args:
            code: Code to refactor
            language: Programming language
            goal: Refactoring goal (improve_readability, optimize_performance, etc.)
            
        Returns:
            Refactored code
        """
        prompt = f"""Refactor the following {language.value} code with goal: {goal}
        
Original code:
{code}

Provide:
1. Refactored code
2. Explanation of changes
3. Performance impact
4. Readability improvements
"""
        
        response = self._call_llm(
            "You are an expert code refactoring assistant.",
            prompt
        )
        
        parsed = self._parse_response(response, None)
        
        return GeneratedCode(
            code=parsed["code"],
            language=language,
            code_type=CodeType.MODULE,
            explanation=parsed.get("explanation"),
            suggestions=parsed.get("suggestions", [])
        )
    
    def optimize(self, code: str, language: Language,
                 metric: str = "speed") -> GeneratedCode:
        """Optimize code for performance
        
        Args:
            code: Code to optimize
            language: Programming language
            metric: Optimization metric (speed, memory, etc.)
            
        Returns:
            Optimized code
        """
        prompt = f"""Optimize the following {language.value} code for {metric}:
        
Original code:
{code}

Provide:
1. Optimized code
2. Performance improvements (%)
3. Trade-offs
4. Benchmarks
"""
        
        response = self._call_llm(
            "You are an expert performance optimization specialist.",
            prompt
        )
        
        parsed = self._parse_response(response, None)
        
        return GeneratedCode(
            code=parsed["code"],
            language=language,
            code_type=CodeType.MODULE,
            explanation=parsed.get("explanation"),
            suggestions=parsed.get("suggestions", [])
        )
    
    def fix_bug(self, code: str, error: str, 
                language: Language) -> GeneratedCode:
        """Fix bugs in code
        
        Args:
            code: Code with bug
            error: Error message or description
            language: Programming language
            
        Returns:
            Fixed code
        """
        prompt = f"""Fix the bug in the following {language.value} code:

Error: {error}

Code:
{code}

Provide:
1. Fixed code
2. Root cause analysis
3. Prevention strategies
4. Test cases to prevent regression
"""
        
        response = self._call_llm(
            "You are an expert debugging specialist.",
            prompt
        )
        
        parsed = self._parse_response(response, None)
        
        return GeneratedCode(
            code=parsed["code"],
            language=language,
            code_type=CodeType.MODULE,
            explanation=parsed.get("explanation"),
            suggestions=parsed.get("suggestions", [])
        )
    
    def _build_system_prompt(self, request: CodeGenerationRequest) -> str:
        """Build system prompt for LLM"""
        return f"""You are an expert {request.language.value} programmer.
Generate high-quality, production-ready code.
Follow best practices and design patterns.
Include error handling and validation.
Write clean, maintainable code.
Optimize for {request.optimization_level}.
"""
    
    def _build_user_prompt(self, request: CodeGenerationRequest) -> str:
        """Build user prompt for LLM"""
        prompt = f"""Generate a {request.code_type.value} in {request.language.value}:

{request.prompt}
"""
        
        if request.context:
            prompt += f"\nContext:\n{request.context}"
        
        if request.style:
            prompt += f"\nStyle: {request.style}"
        
        if request.include_tests:
            prompt += "\nInclude unit tests."
        
        if request.include_docs:
            prompt += "\nInclude documentation."
        
        return prompt
    
    def _call_llm(self, system: str, user: str) -> str:
        """Call LLM to generate code"""
        # This would call the actual LLM API
        # For now, return a mock response
        return f"""
```{self.model}
# Generated code would go here
def example_function():
    '''Example generated function'''
    return "Generated code"
```

Explanation: This is a mock response. In production, this would call the LLM API.
"""
    
    def _parse_response(self, response: str, request: Optional[CodeGenerationRequest]) -> Dict:
        """Parse LLM response"""
        return {
            "code": response,
            "explanation": "Code generated successfully",
            "confidence": 0.85,
            "suggestions": [
                "Add error handling",
                "Add type hints",
                "Add docstrings"
            ]
        }
    
    def _generate_tests(self, code: str, request: CodeGenerationRequest) -> str:
        """Generate tests for code"""
        prompt = f"""Generate unit tests for the following {request.language.value} code:

{code}

Use appropriate testing framework for {request.language.value}.
"""
        
        return self._call_llm("You are an expert test writer.", prompt)
    
    def _generate_documentation(self, code: str, 
                               request: CodeGenerationRequest) -> str:
        """Generate documentation for code"""
        prompt = f"""Generate comprehensive documentation for the following {request.language.value} code:

{code}

Include:
1. Function/class description
2. Parameters
3. Return values
4. Examples
5. Edge cases
"""
        
        return self._call_llm("You are an expert technical writer.", prompt)


class CodeCompletion:
    """AI-powered code completion"""
    
    def __init__(self, model: str = "gpt-4"):
        """Initialize code completion"""
        self.model = model
        self.context_window = 2048
    
    def complete(self, code: str, language: Language, 
                 cursor_position: int) -> List[str]:
        """Get code completions at cursor position
        
        Args:
            code: Current code
            language: Programming language
            cursor_position: Cursor position in code
            
        Returns:
            List of completion suggestions
        """
        # Extract context around cursor
        context = self._extract_context(code, cursor_position)
        
        # Get completions from LLM
        completions = self._get_completions(context, language)
        
        return completions
    
    def _extract_context(self, code: str, position: int) -> str:
        """Extract context around cursor"""
        start = max(0, position - self.context_window)
        end = min(len(code), position + self.context_window)
        return code[start:end]
    
    def _get_completions(self, context: str, language: Language) -> List[str]:
        """Get completions from LLM"""
        # Mock completions
        return [
            "def function_name():",
            "class ClassName:",
            "import module_name",
        ]


class CodeAnalysis:
    """AI-powered code analysis"""
    
    def __init__(self, model: str = "gpt-4"):
        """Initialize code analysis"""
        self.model = model
    
    def analyze(self, code: str, language: Language) -> Dict:
        """Analyze code for issues and improvements
        
        Args:
            code: Code to analyze
            language: Programming language
            
        Returns:
            Analysis results
        """
        return {
            "issues": [
                {"type": "style", "message": "Line too long", "line": 5},
                {"type": "performance", "message": "Inefficient loop", "line": 12},
            ],
            "improvements": [
                "Add type hints",
                "Extract function",
                "Use list comprehension",
            ],
            "complexity": {
                "cyclomatic": 3,
                "cognitive": 5,
            },
            "score": 7.5,
        }
    
    def suggest_improvements(self, code: str, language: Language) -> List[str]:
        """Suggest code improvements
        
        Args:
            code: Code to analyze
            language: Programming language
            
        Returns:
            List of improvement suggestions
        """
        analysis = self.analyze(code, language)
        return analysis.get("improvements", [])
