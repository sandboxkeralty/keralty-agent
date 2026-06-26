import React from 'react';

export function EmailInbox() {
  return (
    <div className="bg-white border border-[var(--color-border)] rounded-lg p-4 shadow-sm">
      <h3 className="font-bold text-lg text-[var(--color-navy)] mb-4">Inbox</h3>
      <div className="space-y-3">
        <div className="p-3 bg-gray-50 rounded border-l-4 border-red-500 flex flex-col cursor-pointer hover:bg-gray-100">
          <div className="flex justify-between items-center mb-1">
            <span className="font-semibold text-sm">CEO Office</span>
            <span className="text-xs font-bold text-red-500 bg-red-100 px-2 py-0.5 rounded">CRITICAL</span>
          </div>
          <p className="text-sm font-medium">Q3 Board Deck Review needed urgently</p>
          <p className="text-xs text-gray-500 mt-1 line-clamp-1">Please review the attached presentation by 2 PM.</p>
        </div>
      </div>
    </div>
  );
}
