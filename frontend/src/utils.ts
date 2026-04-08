import type { RiskBand, Severity } from './types';

export function severityFromLevel(level: string): Severity {
    switch (level) {
        case 'error': return 'CRITICAL';
        case 'warning': return 'MEDIUM';
        case 'note': return 'LOW';
        default: return 'INFO';
    }
}

export function severityColor(severity: Severity): string {
    const map: Record<Severity, string> = {
        CRITICAL: '#c0392b',
        HIGH: '#d35400',
        MEDIUM: '#e67e22',
        LOW: '#2980b9',
        INFO: '#8a8279',
    };
    return map[severity] ?? map.INFO;
}

export function severityBg(severity: Severity): string {
    const map: Record<Severity, string> = {
        CRITICAL: 'bg-severity-critical/15 text-severity-critical border-severity-critical/30',
        HIGH: 'bg-severity-high/15 text-severity-high border-severity-high/30',
        MEDIUM: 'bg-severity-medium/15 text-severity-medium border-severity-medium/30',
        LOW: 'bg-severity-low/15 text-severity-low border-severity-low/30',
        INFO: 'bg-severity-info/15 text-severity-info border-severity-info/30',
    };
    return map[severity] ?? map.INFO;
}

export function riskBand(score: number): RiskBand {
    if (score < 20) return 'pass';
    if (score < 50) return 'warning';
    if (score < 80) return 'critical';
    return 'manual_review';
}

export function riskLabel(band: RiskBand): string {
    const map: Record<RiskBand, string> = {
        pass: 'Safe',
        warning: 'Warning',
        critical: 'Critical',
        manual_review: 'Manual Review',
    };
    return map[band];
}

export function riskColor(band: RiskBand): string {
    const map: Record<RiskBand, string> = {
        pass: 'text-success',
        warning: 'text-warning',
        critical: 'text-severity-critical',
        manual_review: 'text-severity-high',
    };
    return map[band];
}

export function riskBgClass(band: RiskBand): string {
    const map: Record<RiskBand, string> = {
        pass: 'bg-success/8 border-success/20',
        warning: 'bg-warning/8 border-warning/20',
        critical: 'bg-severity-critical/8 border-severity-critical/20',
        manual_review: 'bg-severity-high/8 border-severity-high/20',
    };
    return map[band];
}

export function formatScore(score: number): string {
    return Number.isInteger(score) ? String(score) : score.toFixed(1);
}

export function ruleDisplayName(ruleId: string): string {
    return ruleId
        .replace(/-/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase());
}
