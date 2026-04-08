import type { AnalyzeResponse, AuditJob, AuditReport, ExplainResponse, ExplainLLMResponse } from './types';

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() || '/api';

function buildUrl(path: string): string {
    const normalizedBase = API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE;
    return `${normalizedBase}${path}`;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(buildUrl(path), {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed: ${res.status}`);
    }
    return res.json();
}

export const api = {
    health: () => request<{ ok: boolean }>('/health'),

    analyze: (path: string, full = false) =>
        request<AnalyzeResponse>('/analyze', {
            method: 'POST',
            body: JSON.stringify({ path, full }),
        }),

    explain: (path: string, maxItems?: number) =>
        request<ExplainResponse>('/explain', {
            method: 'POST',
            body: JSON.stringify({ path, max_items: maxItems }),
        }),

    explainLLM: (path: string) =>
        request<ExplainLLMResponse>('/explain-llm', {
            method: 'POST',
            body: JSON.stringify({ path }),
        }),

    audit: (path: string, depth: 'triage' | 'full' = 'triage') =>
        request<AuditJob>('/audit', {
            method: 'POST',
            body: JSON.stringify({ source: { path }, depth }),
        }),

    report: (auditId: string) =>
        request<AuditReport>(`/report/${encodeURIComponent(auditId)}`),
};
