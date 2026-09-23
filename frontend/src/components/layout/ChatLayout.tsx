import type { ReactNode } from 'react';

interface Props {
  sidebar: ReactNode;
  content: ReactNode;
}

export function ChatLayout({ sidebar, content }: Props) {
  return (
    <div className="flex h-screen bg-white">
      <aside className="w-[260px] flex-shrink-0 bg-[#f9f9f9] flex flex-col">
        {sidebar}
      </aside>
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {content}
      </main>
    </div>
  );
}
