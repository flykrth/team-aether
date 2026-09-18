import React from 'react';

// Minimal inline formatting: **bold** and `code`. Everything else stays plain text.
const inline = (text) =>
  text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((chunk, i) => {
    if (chunk.startsWith('**') && chunk.endsWith('**') && chunk.length > 4) return <strong key={i} className="font-semibold">{chunk.slice(2, -2)}</strong>;
    if (chunk.startsWith('`') && chunk.endsWith('`') && chunk.length > 2) return <code key={i} className="font-mono text-[0.85em] bg-app-secondary rounded px-1 py-0.5">{chunk.slice(1, -1)}</code>;
    return <React.Fragment key={i}>{chunk}</React.Fragment>;
  });

// Block formatting the models actually produce: paragraphs, "- " / "* " / "1. " lists and "#" headings.
export function FormattedText({ text }) {
  const blocks = [];
  let list = null;
  (text || '').split('\n').forEach((raw) => {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);
    if (bullet) {
      if (!list) { list = []; blocks.push({ list }); }
      list.push(bullet[1]);
      return;
    }
    list = null;
    const heading = line.match(/^#{1,4}\s+(.*)$/);
    if (heading) blocks.push({ heading: heading[1] });
    else if (line.trim()) blocks.push({ text: line });
  });

  return (
    <div className="space-y-2 break-words">
      {blocks.map((b, i) => {
        if (b.list) {
          return (
            <ul key={i} className="space-y-1">
              {b.list.map((item, j) => (
                <li key={j} className="flex gap-2.5">
                  <span className="mt-[0.6em] w-1 h-1 rounded-full bg-current opacity-40 shrink-0" />
                  <span className="min-w-0">{inline(item)}</span>
                </li>
              ))}
            </ul>
          );
        }
        if (b.heading) return <p key={i} className="font-display font-semibold">{inline(b.heading)}</p>;
        return <p key={i}>{inline(b.text)}</p>;
      })}
    </div>
  );
}
