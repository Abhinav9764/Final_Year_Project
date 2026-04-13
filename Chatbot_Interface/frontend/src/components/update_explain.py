import re
with open('ExplainPanel.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Add imports
imports = '''import React, { useState, useEffect } from 'react'
import { apiUrl } from '../lib/api.js'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
'''
content = content.replace("import React, { useState, useEffect } from 'react'\nimport { apiUrl } from '../lib/api.js'", imports, 1)

# Modify CodeTab
code_tab_search = '''        <pre style={{
          margin: 0, padding: '12px 14px',
          height: 'calc(100% - 36px)', overflowY: 'auto',
          fontFamily: 'var(--font-mono)', fontSize: 11.5,
          lineHeight: 1.65, color: 'var(--text2)',
          whiteSpace: 'pre-wrap', wordBreak: 'break-word',
        }}>
          {_syntaxHighlight(activeFile || '', preview[activeFile] || '')}
        </pre>'''

code_tab_replace = '''        <div style={{ height: 'calc(100% - 36px)', overflowY: 'auto' }}>
          <SyntaxHighlighter
            language={activeFile?.endsWith('.py') ? 'python' : 'bash'}
            style={vscDarkPlus}
            customStyle={{ margin: 0, padding: '12px 14px', background: 'transparent', fontSize: '11.5px', fontFamily: 'var(--font-mono)' }}
            showLineNumbers={true}
          >
            {preview[activeFile] || ''}
          </SyntaxHighlighter>
        </div>'''
content = content.replace(code_tab_search, code_tab_replace)

with open('ExplainPanel.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
