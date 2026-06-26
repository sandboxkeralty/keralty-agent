import React from 'react';

interface OrgChartCardProps {
  name: string;
  role: string;
  department: string;
  reportsTo?: string;
  directReports?: string[];
}

export function OrgChartCard({ name, role, department, reportsTo, directReports }: OrgChartCardProps) {
  return (
    <div className="bg-white border border-[var(--color-border)] rounded-lg p-4 shadow-sm my-2 border-l-4 border-l-[var(--color-primary)]">
      <h4 className="font-bold text-[var(--color-navy)] text-lg">{name}</h4>
      <p className="text-sm font-medium text-[var(--color-primary)]">{role}</p>
      <p className="text-sm text-[var(--color-text-muted)] mb-3">{department}</p>
      
      {reportsTo && (
        <div className="mb-2">
          <span className="text-xs text-gray-500 uppercase font-semibold">Reports To</span>
          <p className="text-sm">{reportsTo}</p>
        </div>
      )}
      
      {directReports && directReports.length > 0 && (
        <div>
          <span className="text-xs text-gray-500 uppercase font-semibold">Direct Reports</span>
          <ul className="text-sm list-disc pl-4 mt-1">
            {directReports.map((report, idx) => (
              <li key={idx}>{report}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
