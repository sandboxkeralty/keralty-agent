import React from 'react';

export function EmailTrackingPanel() {
  return (
    <div className="bg-white border border-[var(--color-border)] rounded-lg p-4 shadow-sm">
      <h3 className="font-bold text-lg text-[var(--color-navy)] mb-4">Awaiting Response</h3>
      <div className="space-y-3">
        <div className="flex justify-between items-center border-b border-gray-100 pb-2">
          <div>
            <p className="text-sm font-semibold">Vendor Contract Approval</p>
            <p className="text-xs text-gray-500">Sent to: Legal Dept</p>
          </div>
          <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">2 days ago</span>
        </div>
      </div>
    </div>
  );
}
