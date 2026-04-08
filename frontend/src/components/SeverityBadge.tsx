import type { Severity } from '../types';
import { severityBg } from '../utils';

interface Props {
    severity: Severity;
    size?: 'sm' | 'md';
}

export default function SeverityBadge({ severity, size = 'sm' }: Props) {
    const sizeClass = size === 'sm' ? 'text-[10px] px-2 py-0.5' : 'text-xs px-2.5 py-1';
    return (
        <span className={`inline-flex items-center font-semibold rounded-full border ${severityBg(severity)} ${sizeClass} tracking-wide uppercase`}>
            {severity}
        </span>
    );
}
