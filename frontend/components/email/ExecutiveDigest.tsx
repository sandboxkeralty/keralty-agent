import React from 'react';

export function ExecutiveDigest() {
  return (
    <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100 rounded-lg p-5 shadow-sm">
      <h2 className="text-xl font-bold text-[var(--color-navy)] mb-4">Daily Executive Digest</h2>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white p-3 rounded shadow-sm text-center">
          <span className="text-2xl font-bold text-[var(--color-primary)]">42</span>
          <p className="text-xs text-gray-500 uppercase">Emails Received</p>
        </div>
        <div className="bg-white p-3 rounded shadow-sm text-center">
          <span className="text-2xl font-bold text-red-500">2</span>
          <p className="text-xs text-gray-500 uppercase">Critical</p>
        </div>
        <div className="bg-white p-3 rounded shadow-sm text-center">
          <span className="text-2xl font-bold text-orange-500">5</span>
          <p className="text-xs text-gray-500 uppercase">Action Items</p>
        </div>
        <div className="bg-white p-3 rounded shadow-sm text-center">
          <span className="text-2xl font-bold text-yellow-600">3</span>
          <p className="text-xs text-gray-500 uppercase">Awaiting Reply</p>
        </div>
      </div>

      <div className="bg-white p-4 rounded shadow-sm">
        <h3 className="font-semibold text-[var(--color-primary)] mb-3">Priority Actions</h3>
        <ul className="space-y-2 text-sm">
          <li className="flex items-start gap-2">
            <span className="mt-1 flex-shrink-0 w-2 h-2 rounded-full bg-red-500"></span>
            <span>Review Q3 Board Deck by 2 PM (CEO Office)</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-1 flex-shrink-0 w-2 h-2 rounded-full bg-orange-500"></span>
            <span>Approve budget transfer request (Finance)</span>
          </li>
        </ul>
      </div>
    </div>
  );
}
