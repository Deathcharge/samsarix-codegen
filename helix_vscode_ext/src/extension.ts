import * as vscode from 'vscode';
import { CodeGenerationProvider } from './providers/codeGeneration';
import { CodeCompletionProvider } from './providers/codeCompletion';
import { CodeAnalysisProvider } from './providers/codeAnalysis';
import { HelixStatusBar } from './ui/statusBar';
import { HelixSidebar } from './ui/sidebar';

let statusBar: HelixStatusBar;
let sidebar: HelixSidebar;

export function activate(context: vscode.ExtensionContext) {
    console.log('Helix AI Extension activated');

    // Initialize UI components
    statusBar = new HelixStatusBar();
    sidebar = new HelixSidebar(context);

    // Register code generation provider
    const codeGenProvider = new CodeGenerationProvider();
    context.subscriptions.push(
        vscode.commands.registerCommand('helix.generate.function', () => 
            codeGenProvider.generateFunction()
        ),
        vscode.commands.registerCommand('helix.generate.class', () => 
            codeGenProvider.generateClass()
        ),
        vscode.commands.registerCommand('helix.generate.test', () => 
            codeGenProvider.generateTest()
        ),
        vscode.commands.registerCommand('helix.generate.docs', () => 
            codeGenProvider.generateDocumentation()
        )
    );

    // Register code completion provider
    const completionProvider = new CodeCompletionProvider();
    context.subscriptions.push(
        vscode.languages.registerCompletionItemProvider(
            { scheme: 'file', language: 'python' },
            completionProvider,
            '.'
        ),
        vscode.languages.registerCompletionItemProvider(
            { scheme: 'file', language: 'typescript' },
            completionProvider,
            '.'
        ),
        vscode.languages.registerCompletionItemProvider(
            { scheme: 'file', language: 'javascript' },
            completionProvider,
            '.'
        )
    );

    // Register code analysis provider
    const analysisProvider = new CodeAnalysisProvider();
    context.subscriptions.push(
        vscode.commands.registerCommand('helix.analyze.file', () =>
            analysisProvider.analyzeFile()
        ),
        vscode.commands.registerCommand('helix.analyze.selection', () =>
            analysisProvider.analyzeSelection()
        ),
        vscode.commands.registerCommand('helix.refactor.code', () =>
            analysisProvider.refactorCode()
        ),
        vscode.commands.registerCommand('helix.optimize.performance', () =>
            analysisProvider.optimizePerformance()
        ),
        vscode.commands.registerCommand('helix.fix.bug', () =>
            analysisProvider.fixBug()
        )
    );

    // Register interactive mode
    context.subscriptions.push(
        vscode.commands.registerCommand('helix.interactive.start', () =>
            startInteractiveMode(context)
        ),
        vscode.commands.registerCommand('helix.interactive.explain', () =>
            explainCode()
        ),
        vscode.commands.registerCommand('helix.interactive.suggest', () =>
            suggestImprovements()
        )
    );

    // Register hover provider for inline help
    context.subscriptions.push(
        vscode.languages.registerHoverProvider(
            { scheme: 'file' },
            {
                provideHover: (document, position, token) =>
                    provideHover(document, position)
            }
        )
    );

    // Register code lens for quick actions
    context.subscriptions.push(
        vscode.languages.registerCodeLensProvider(
            { scheme: 'file' },
            {
                provideCodeLenses: (document, token) =>
                    provideCodeLenses(document)
            }
        )
    );

    // Update status bar
    statusBar.update('Helix AI Ready', 'green');

    console.log('Helix AI Extension fully initialized');
}

async function startInteractiveMode(context: vscode.ExtensionContext) {
    const panel = vscode.window.createWebviewPanel(
        'helixInteractive',
        'Helix AI Assistant',
        vscode.ViewColumn.Beside,
        { enableScripts: true }
    );

    panel.webview.html = getWebviewContent();

    // Handle messages from webview
    panel.webview.onDidReceiveMessage(
        (message) => {
            handleInteractiveMessage(message, context);
        },
        undefined,
        context.subscriptions
    );
}

async function explainCode() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showErrorMessage('No active editor');
        return;
    }

    const selection = editor.selection;
    const code = editor.document.getText(selection);

    if (!code) {
        vscode.window.showErrorMessage('No code selected');
        return;
    }

    vscode.window.showInformationMessage('Explaining code...');
    
    // Call Helix API to explain code
    const explanation = await explainCodeViaAPI(code);
    
    vscode.window.showInformationMessage(explanation);
}

async function suggestImprovements() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showErrorMessage('No active editor');
        return;
    }

    const code = editor.document.getText();
    
    vscode.window.showInformationMessage('Analyzing code...');
    
    // Call Helix API for suggestions
    const suggestions = await getSuggestionsViaAPI(code);
    
    // Show suggestions in quick pick
    const selected = await vscode.window.showQuickPick(suggestions);
    
    if (selected) {
        vscode.window.showInformationMessage(`Suggestion: ${selected}`);
    }
}

function provideHover(
    document: vscode.TextDocument,
    position: vscode.Position
): vscode.Hover | undefined {
    const range = document.getWordRangeAtPosition(position);
    if (!range) {
        return undefined;
    }

    const word = document.getText(range);
    
    // Return hover information
    return new vscode.Hover(new vscode.MarkdownString(
        `**${word}**\n\nHelix AI can help you:\n- Generate code\n- Explain this\n- Suggest improvements`
    ));
}

function provideCodeLenses(document: vscode.TextDocument): vscode.CodeLens[] {
    const codeLenses: vscode.CodeLens[] = [];
    
    // Add code lens for functions
    const functionRegex = /^(async\s+)?function\s+(\w+)|^const\s+(\w+)\s*=\s*(async\s*)?\(/gm;
    let match;
    
    while ((match = functionRegex.exec(document.getText())) !== null) {
        const line = document.lineAt(document.positionAt(match.index).line);
        const range = new vscode.Range(line.range.start, line.range.end);
        
        codeLenses.push(
            new vscode.CodeLens(range, {
                title: '✨ Generate Tests',
                command: 'helix.generate.test',
            }),
            new vscode.CodeLens(range, {
                title: '📚 Generate Docs',
                command: 'helix.generate.docs',
            }),
            new vscode.CodeLens(range, {
                title: '⚡ Optimize',
                command: 'helix.optimize.performance',
            })
        );
    }
    
    return codeLenses;
}

function handleInteractiveMessage(message: any, context: vscode.ExtensionContext) {
    switch (message.command) {
        case 'generate':
            vscode.commands.executeCommand('helix.generate.function');
            break;
        case 'analyze':
            vscode.commands.executeCommand('helix.analyze.file');
            break;
        case 'explain':
            vscode.commands.executeCommand('helix.interactive.explain');
            break;
        case 'suggest':
            vscode.commands.executeCommand('helix.interactive.suggest');
            break;
    }
}

async function explainCodeViaAPI(code: string): Promise<string> {
    // Call Helix API
    return `This code does X, Y, and Z. Here are suggestions for improvement...`;
}

async function getSuggestionsViaAPI(code: string): Promise<string[]> {
    // Call Helix API
    return [
        'Add type hints',
        'Extract function',
        'Use list comprehension',
        'Add error handling',
    ];
}

function getWebviewContent(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Helix AI Assistant</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            padding: 20px;
            background: #1e1e1e;
            color: #e0e0e0;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        h1 {
            color: #61dafb;
            margin-bottom: 20px;
        }
        .button-group {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 20px;
        }
        button {
            padding: 10px 15px;
            background: #007acc;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        button:hover {
            background: #005a9e;
        }
        .chat-area {
            background: #252526;
            border: 1px solid #3e3e42;
            border-radius: 4px;
            padding: 15px;
            height: 300px;
            overflow-y: auto;
            margin-bottom: 15px;
        }
        .message {
            margin-bottom: 10px;
            padding: 8px;
            border-radius: 4px;
        }
        .message.user {
            background: #007acc;
            text-align: right;
        }
        .message.assistant {
            background: #3e3e42;
        }
        input {
            width: 100%;
            padding: 10px;
            background: #3e3e42;
            color: #e0e0e0;
            border: 1px solid #555;
            border-radius: 4px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>✨ Helix AI Assistant</h1>
        
        <div class="button-group">
            <button onclick="sendCommand('generate')">🚀 Generate</button>
            <button onclick="sendCommand('analyze')">🔍 Analyze</button>
            <button onclick="sendCommand('explain')">📖 Explain</button>
            <button onclick="sendCommand('suggest')">💡 Suggest</button>
        </div>
        
        <div class="chat-area" id="chatArea">
            <div class="message assistant">
                Hello! I'm Helix AI. I can help you generate code, analyze your code, explain it, and suggest improvements. What would you like to do?
            </div>
        </div>
        
        <input type="text" id="input" placeholder="Ask me anything..." onkeypress="handleKeyPress(event)">
    </div>
    
    <script>
        const vscode = acquireVsCodeApi();
        
        function sendCommand(command) {
            vscode.postMessage({ command });
        }
        
        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                const input = document.getElementById('input');
                const message = input.value;
                if (message) {
                    addMessage(message, 'user');
                    vscode.postMessage({ command: 'chat', message });
                    input.value = '';
                }
            }
        }
        
        function addMessage(text, role) {
            const chatArea = document.getElementById('chatArea');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message ' + role;
            messageDiv.textContent = text;
            chatArea.appendChild(messageDiv);
            chatArea.scrollTop = chatArea.scrollHeight;
        }
        
        window.addEventListener('message', event => {
            const message = event.data;
            if (message.type === 'response') {
                addMessage(message.text, 'assistant');
            }
        });
    </script>
</body>
</html>`;
}

export function deactivate() {
    console.log('Helix AI Extension deactivated');
}
