import Editor from '@monaco-editor/react';

export default function CodeEditor({ language, value, onChange }) {
  return (
    <div className="editor-shell">
      <Editor
        height="100%"
        language={language}
        value={value}
        onChange={(v) => onChange(v ?? '')}
        theme="vs-dark"
        options={{
          minimap: { enabled: false },
          fontSize: 13,
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
          tabSize: 2,
          automaticLayout: true,
        }}
      />
    </div>
  );
}
