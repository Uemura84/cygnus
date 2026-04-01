/**
 * Minimal markdown renderer — no extra deps.
 * Supports: ## h2, ### h3, **bold**, - lists, numbered lists, | tables, paragraphs.
 * Designed to work on partially-streamed text gracefully.
 */

function renderInline(text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i}>{part.slice(2, -2)}</strong>
    }
    return part
  })
}

function parseTableRow(line) {
  return line.split('|').slice(1, -1).map((c) => c.trim())
}

function isSeparatorRow(line) {
  return /^\|[-| :]+\|$/.test(line.trim())
}

export default function MarkdownView({ text }) {
  const lines    = text.split('\n')
  const output   = []
  let listItems  = []
  let listType   = null   // 'ul' | 'ol'
  let tableLines = []

  function flushList() {
    if (!listItems.length) return
    const Tag = listType === 'ol' ? 'ol' : 'ul'
    output.push(
      <Tag key={`list-${output.length}`} style={{ paddingLeft: '20px', margin: '6px 0 10px' }}>
        {listItems.map((item, j) => (
          <li key={j} style={{ marginBottom: '3px' }}>{renderInline(item)}</li>
        ))}
      </Tag>
    )
    listItems = []
    listType  = null
  }

  function flushTable() {
    if (!tableLines.length) return
    const sepIdx    = tableLines.findIndex(isSeparatorRow)
    const headerLines = sepIdx >= 1 ? tableLines.slice(0, sepIdx) : []
    const dataLines   = sepIdx >= 0 ? tableLines.slice(sepIdx + 1) : tableLines

    output.push(
      <div key={`table-${output.length}`} style={{ overflowX: 'auto', margin: '12px 0' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '0.82rem' }}>
          {headerLines.length > 0 && (
            <thead>
              {headerLines.map((row, i) => (
                <tr key={i}>
                  {parseTableRow(row).map((cell, j) => (
                    <th key={j} style={{
                      padding: '7px 12px',
                      borderBottom: '2px solid #cbd5e1',
                      textAlign: 'left',
                      fontWeight: 700,
                      color: '#1e293b',
                      whiteSpace: 'nowrap',
                      background: '#f8fafc',
                    }}>
                      {renderInline(cell)}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
          )}
          <tbody>
            {dataLines.map((row, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #f1f5f9' }}>
                {parseTableRow(row).map((cell, j) => (
                  <td key={j} style={{ padding: '6px 12px', color: '#475569', verticalAlign: 'top' }}>
                    {renderInline(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
    tableLines = []
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    if (line.trimStart().startsWith('|')) {
      flushList()
      tableLines.push(line)
      continue
    }

    // Blank lines inside an active table (LLM often emits one blank line per row) — skip
    if (tableLines.length > 0 && line.trim() === '') continue

    flushTable()

    if (line.startsWith('## ')) {
      flushList()
      output.push(
        <h2 key={i} style={{ fontSize: '1rem', fontWeight: 700, margin: '18px 0 6px', color: '#0f172a', borderBottom: '1px solid #e2e8f0', paddingBottom: '4px' }}>
          {renderInline(line.slice(3))}
        </h2>
      )
    } else if (line.startsWith('### ')) {
      flushList()
      output.push(
        <h3 key={i} style={{ fontSize: '0.9rem', fontWeight: 700, margin: '14px 0 4px', color: '#1e293b' }}>
          {renderInline(line.slice(4))}
        </h3>
      )
    } else if (/^[-*] /.test(line)) {
      listType = 'ul'
      listItems.push(line.slice(2))
    } else if (/^\d+\. /.test(line)) {
      listType = 'ol'
      listItems.push(line.replace(/^\d+\. /, ''))
    } else if (line.trim() === '') {
      flushList()
    } else {
      flushList()
      output.push(
        <p key={i} style={{ margin: '4px 0 8px', lineHeight: 1.7 }}>
          {renderInline(line)}
        </p>
      )
    }
  }

  flushList()
  flushTable()
  return <div>{output}</div>
}
