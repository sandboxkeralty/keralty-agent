import React from 'react';

export function EmailDraftCard() {
  return (
    <div className="bg-white border border-[var(--color-border)] rounded-lg p-4 shadow-sm border-l-4 border-l-orange-400">
      <div className="flex justify-between items-center mb-3">
        <h4 className="font-bold text-md text-[var(--color-navy)]">Draft Approval Required</h4>
        <span className="text-xs bg-orange-100 text-orange-800 px-2 py-1 rounded-full font-medium">Pending Review</span>
      </div>
      <div className="mb-3 space-y-2">
        <div className="text-sm"><span className="text-gray-500 w-12 inline-block">To:</span> ceo.office@keralty.com</div>
        <div className="text-sm"><span className="text-gray-500 w-12 inline-block">Subj:</span> Re: Q3 Board Deck Review</div>
      </div>
      <div className="p-3 bg-gray-50 rounded text-sm text-gray-700 whitespace-pre-wrap border border-gray-100">
        I have reviewed the deck. Looks good to me. No further edits.
      </div>
      <div className="mt-4 flex gap-2 justify-end">
        <button className="px-3 py-1.5 text-sm bg-gray-200 hover:bg-gray-300 rounded transition-colors">Discard</button>
        <button className="px-3 py-1.5 text-sm bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] text-white rounded transition-colors">Approve & Send</button>
      </div>
    </div>
  );
}
