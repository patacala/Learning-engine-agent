import type { TemporaryDocument } from '../../types/testing';
import { DOC_CATEGORIES } from '../../constants/testingTemplates';

interface Props {
  doc: TemporaryDocument;
  onChange: (patch: Partial<TemporaryDocument>) => void;
  onRemove: () => void;
}

export function DocumentCard({ doc, onChange, onRemove }: Props) {
  return (
    <div className="border border-[#e3e3e3] rounded-lg p-2.5 bg-white">
      <div className="flex items-center gap-2 mb-2">
        <input
          value={doc.title}
          onChange={(e) => onChange({ title: e.target.value })}
          placeholder="Document title"
          className="flex-1 min-w-0 text-[13px] text-[#0d0d0d] bg-transparent border-b border-transparent focus:border-[#e3e3e3] focus:outline-none py-0.5"
        />
        <select
          value={doc.category}
          onChange={(e) => onChange({ category: e.target.value })}
          className="text-[11px] text-[#6e6e80] bg-transparent border border-[#e3e3e3] rounded-md px-1.5 py-1 focus:outline-none cursor-pointer"
        >
          {DOC_CATEGORIES.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
        <button
          onClick={onRemove}
          className="w-6 h-6 flex items-center justify-center rounded-md text-[#b3b3b3] hover:bg-[#f4f4f4] hover:text-[#0d0d0d] transition-colors"
          title="Remove document"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>
      <textarea
        value={doc.content}
        onChange={(e) => onChange({ content: e.target.value })}
        placeholder="Content: prices, features, policies, inventory..."
        rows={3}
        className="w-full text-[12px] text-[#0d0d0d] bg-[#fafafa] border border-[#ececec] rounded-md px-2 py-1.5 focus:outline-none focus:border-[#b3b3b3] resize-y"
      />
    </div>
  );
}
