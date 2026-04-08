import { FileCode2, MapPin } from 'lucide-react';
import SeverityBadge from './SeverityBadge';
import type { Finding } from '../types';
import { severityFromLevel, ruleDisplayName } from '../utils';

interface Props {
    finding: Finding;
    index: number;
}

export default function FindingCard({ finding, index }: Props) {
    const severity = severityFromLevel(finding.level);

    return (
        <div
            className="bg-white border border-border rounded-xl p-5 hover:border-border-light hover:shadow-md transition-all duration-200 animate-fade-in shadow-sm"
            style={{ animationDelay: `${index * 60}ms` }}
        >
            <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-text-primary truncate">
                        {ruleDisplayName(finding.ruleId)}
                    </h3>
                    <span className="text-xs text-text-muted font-mono">{finding.ruleId}</span>
                </div>
                <SeverityBadge severity={severity} />
            </div>

            <p className="text-sm text-text-secondary leading-relaxed mb-4 line-clamp-3">
                {finding.message}
            </p>

            <div className="flex items-center gap-4 text-xs text-text-muted">
                <span className="inline-flex items-center gap-1.5">
                    <FileCode2 className="w-3.5 h-3.5" />
                    {finding.location.file}
                </span>
                <span className="inline-flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5" />
                    Line {finding.location.startLine}
                </span>
                {finding.score > 0 && (
                    <span className="ml-auto font-medium text-accent">
                        Score: {(finding.score * 100).toFixed(0)}
                    </span>
                )}
            </div>
        </div>
    );
}
