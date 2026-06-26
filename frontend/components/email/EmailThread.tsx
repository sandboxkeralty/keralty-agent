import React from 'react';

export function EmailThread() {
  return (
    <div className="bg-white border border-[var(--color-border)] rounded-lg p-4 shadow-sm h-full flex flex-col">
      <h3 className="font-bold text-lg text-[var(--color-navy)] mb-2">Q3 Board Deck Review needed urgently</h3>
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        <div className="bg-blue-50 p-3 rounded-lg border border-blue-100">
          <div className="flex justify-between text-xs text-gray-500 mb-2">
            <span className="font-semibold text-blue-900">CEO Office</span>
            <span>10:30 AM</span>
          </div>
          <p className="text-sm">Please review the attached presentation by 2 PM today.</p>
        </div>
      </div>
    </div>
  );
}
