/**
 * cpp-highlight.js - Lightweight C++ syntax highlighter
 *
 * Categories:
 *   - keyword     : Language keywords (const, while, if, etc.)
 *   - string      : String and character literals
 *   - preprocessor: Preprocessor directives (#include, #define, etc.)
 *   - comment     : C and C++ style comments
 *   - attribute   : C++ attributes ([[nodiscard]], [[noreturn]], etc.)
 */

const CppHighlight = (function () {
  'use strict';

  const KEYWORDS = new Set([
    // Storage class
    'auto',
    'register',
    'static',
    'extern',
    'mutable',
    'thread_local',
    // Type qualifiers
    'const',
    'volatile',
    'constexpr',
    'consteval',
    'constinit',
    // Type specifiers
    'void',
    'bool',
    'char',
    'short',
    'int',
    'long',
    'float',
    'double',
    'signed',
    'unsigned',
    'wchar_t',
    'char8_t',
    'char16_t',
    'char32_t',
    // Complex types
    'class',
    'struct',
    'union',
    'enum',
    'typename',
    'typedef',
    // Control flow
    'if',
    'else',
    'switch',
    'case',
    'default',
    'for',
    'while',
    'do',
    'break',
    'continue',
    'return',
    'goto',
    // Exception handling
    'try',
    'catch',
    'throw',
    'noexcept',
    // OOP
    'public',
    'private',
    'protected',
    'virtual',
    'override',
    'final',
    'friend',
    'this',
    'operator',
    'new',
    'delete',
    // Templates
    'template',
    'concept',
    'requires',
    // Namespace
    'namespace',
    'using',
    // Other
    'sizeof',
    'alignof',
    'alignas',
    'decltype',
    'typeid',
    'static_cast',
    'dynamic_cast',
    'const_cast',
    'reinterpret_cast',
    'static_assert',
    'inline',
    'explicit',
    'export',
    'module',
    'import',
    'co_await',
    'co_yield',
    'co_return',
    // Literals
    'true',
    'false',
    'nullptr',
    'NULL',
  ]);

  function escapeHtml(text) {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function span(cls, content) {
    return `<span class="cpp-${cls}">${escapeHtml(content)}</span>`;
  }

  function highlight(code) {
    const result = [];
    let i = 0;
    const n = code.length;

    while (i < n) {
      // C++ attributes [[...]] with nesting support
      if (code[i] === '[' && code[i + 1] === '[') {
        const start = i;
        i += 2;
        let depth = 1;
        while (i < n && depth > 0) {
          if (code[i] === '[' && code[i + 1] === '[') {
            depth++;
            i += 2;
          } else if (code[i] === ']' && code[i + 1] === ']') {
            depth--;
            i += 2;
          } else {
            i++;
          }
        }
        result.push(span('attribute', code.slice(start, i)));
        continue;
      }

      // Line comment
      if (code[i] === '/' && code[i + 1] === '/') {
        let end = i + 2;
        while (end < n && code[end] !== '\n') end++;
        result.push(span('comment', code.slice(i, end)));
        i = end;
        continue;
      }

      // Block comment
      if (code[i] === '/' && code[i + 1] === '*') {
        let end = i + 2;
        while (end < n - 1 && !(code[end] === '*' && code[end + 1] === '/'))
          end++;
        end += 2;
        result.push(span('comment', code.slice(i, end)));
        i = end;
        continue;
      }

      // Preprocessor directive (at start of line or after whitespace)
      if (code[i] === '#') {
        // Check if # is at line start (allow leading whitespace)
        let checkPos = i - 1;
        while (
          checkPos >= 0 &&
          (code[checkPos] === ' ' || code[checkPos] === '\t')
        )
          checkPos--;
        if (checkPos < 0 || code[checkPos] === '\n') {
          let end = i + 1;
          // Handle line continuation with backslash
          while (end < n) {
            if (code[end] === '\n') {
              if (code[end - 1] === '\\') {
                end++;
                continue;
              }
              break;
            }
            end++;
          }
          result.push(span('preprocessor', code.slice(i, end)));
          i = end;
          continue;
        }
      }

      // Raw string literal R"delimiter(...)delimiter"
      if (code[i] === 'R' && code[i + 1] === '"') {
        let delimEnd = i + 2;
        while (delimEnd < n && code[delimEnd] !== '(') delimEnd++;
        const delimiter = code.slice(i + 2, delimEnd);
        const endMarker = ')' + delimiter + '"';
        let end = delimEnd + 1;
        while (end < n) {
          if (code.slice(end, end + endMarker.length) === endMarker) {
            end += endMarker.length;
            break;
          }
          end++;
        }
        result.push(span('string', code.slice(i, end)));
        i = end;
        continue;
      }

      // String literal (with optional prefix)
      if (
        code[i] === '"' ||
        ((code[i] === 'L' || code[i] === 'u' || code[i] === 'U') &&
          code[i + 1] === '"') ||
        (code[i] === 'u' && code[i + 1] === '8' && code[i + 2] === '"')
      ) {
        const start = i;
        if (code[i] === 'u' && code[i + 1] === '8') i += 2;
        else if (code[i] !== '"') i++;
        i++; // skip opening quote
        while (i < n && code[i] !== '"') {
          if (code[i] === '\\' && i + 1 < n) i += 2;
          else i++;
        }
        i++; // skip closing quote
        result.push(span('string', code.slice(start, i)));
        continue;
      }

      // Character literal
      if (
        code[i] === "'" ||
        ((code[i] === 'L' || code[i] === 'u' || code[i] === 'U') &&
          code[i + 1] === "'") ||
        (code[i] === 'u' && code[i + 1] === '8' && code[i + 2] === "'")
      ) {
        const start = i;
        if (code[i] === 'u' && code[i + 1] === '8') i += 2;
        else if (code[i] !== "'") i++;
        i++; // skip opening quote
        while (i < n && code[i] !== "'") {
          if (code[i] === '\\' && i + 1 < n) i += 2;
          else i++;
        }
        i++; // skip closing quote
        result.push(span('string', code.slice(start, i)));
        continue;
      }

      // Numeric literal (integer or float, with optional suffix)
      if (/[0-9]/.test(code[i])) {
        const start = i;
        if (code[i] === '0' && i + 2 <= n) {
          if (code[i + 1] === 'x' || code[i + 1] === 'X') {
            i += 2;
            while (i < n && /[0-9a-fA-F]/.test(code[i])) i++;
          } else if (code[i + 1] === 'b' || code[i + 1] === 'B') {
            i += 2;
            while (i < n && /[01]/.test(code[i])) i++;
          } else if (/[0-7]/.test(code[i + 1])) {
            i++;
            while (i < n && /[0-7]/.test(code[i])) i++;
          } else {
            i++;
          }
        } else {
          while (i < n && /[0-9]/.test(code[i])) i++;
        }
        if (i < n && code[i] === '.' && /[0-9]/.test(code[i + 1])) {
          i++;
          while (i < n && /[0-9]/.test(code[i])) i++;
        }
        if (i < n && (code[i] === 'e' || code[i] === 'E')) {
          i++;
          if (i < n && (code[i] === '+' || code[i] === '-')) i++;
          while (i < n && /[0-9]/.test(code[i])) i++;
        }
        while (i < n && /[fFlLuU]/.test(code[i])) i++;
        result.push(span('number', code.slice(start, i)));
        continue;
      }

      // Identifier or keyword
      if (/[a-zA-Z_]/.test(code[i])) {
        let end = i + 1;
        while (end < n && /[a-zA-Z0-9_]/.test(code[end])) end++;
        const word = code.slice(i, end);
        let j = end;
        while (j < n && (code[j] === ' ' || code[j] === '\t')) j++;
        const isFunctionCall = j < n && code[j] === '(';
        if (KEYWORDS.has(word)) {
          result.push(span('keyword', word));
        } else if (isFunctionCall) {
          result.push(span('function', word));
        } else {
          result.push(escapeHtml(word));
        }
        i = end;
        continue;
      }

      // Default: single character
      result.push(escapeHtml(code[i]));
      i++;
    }

    return result.join('');
  }

  function highlightElement(el) {
    el.innerHTML = highlight(el.textContent);
  }

  function highlightAll(selector = 'code.cpp, code.c++, pre.cpp, pre.c++') {
    document.querySelectorAll(selector).forEach(highlightElement);
  }

  return {
    highlight,
    highlightElement,
    highlightAll,
    KEYWORDS,
  };
})();

// Browser global (for script tag usage)
if (typeof window !== 'undefined') {
  window.CppHighlight = CppHighlight;
}
// CommonJS / ES module support
if (typeof module !== 'undefined' && module.exports) {
  module.exports = CppHighlight;
}
