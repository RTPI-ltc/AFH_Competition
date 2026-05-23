import type { RiskItem } from '../../types';
import { AlertTriangle } from 'lucide-react';

interface RiskAlertProps {
  risks: RiskItem[];
}

const severityStyles = {
  high: 'border-red-300 bg-red-50',
  medium: 'border-amber-300 bg-amber-50',
};

export function RiskAlert({ risks }: RiskAlertProps) {
  return (
    <div className="mt-3 space-y-2">
      {risks.map((risk, idx) => (
        <div
          key={idx}
          className={`flex items-start gap-3 px-4 py-3 border rounded-xl ${severityStyles[risk.severity]}`}
        >
          <AlertTriangle
            size={16}
            className={`shrink-0 mt-0.5 ${
              risk.severity === 'high' ? 'text-red-500' : 'text-amber-500'
            }`}
          />
          <div>
            <p className={`text-sm ${
              risk.severity === 'high' ? 'text-red-800' : 'text-amber-800'
            }`}>
              {risk.description}
            </p>
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium mt-1 inline-block ${
              risk.severity === 'high'
                ? 'bg-red-200 text-red-700'
                : 'bg-amber-200 text-amber-700'
            }`}>
              {risk.severity === 'high' ? '高风险' : '中风险'}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
