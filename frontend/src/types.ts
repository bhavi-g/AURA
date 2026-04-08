export interface Finding {
    ruleId: string;
    level: 'error' | 'warning' | 'note';
    message: string;
    location: {
        file: string;
        startLine: number;
    };
    score: number;
    tool: string;
}

export interface AuditReport {
    status: 'queued' | 'running' | 'ready' | 'error';
    report?: {
        summary: { ok: boolean };
        details: {
            score: number;
            n_findings: number;
            reports: Finding[];
        };
    };
    error?: string;
}

export interface AnalyzeResponse {
    score: number;
    reports: Finding[];
    n_findings: number;
}

export interface ExplainResponse {
    summary: string;
    n_findings: number;
    score: number;
    top_findings: {
        rule_id: string;
        title: string;
        severity: string;
        score: number;
        description: string;
    }[];
}

export interface ExplainLLMResponse {
    explanation: string;
}

export interface AuditJob {
    job_id: string;
    status: string;
}

export type Severity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

export type RiskBand = 'pass' | 'warning' | 'critical' | 'manual_review';
