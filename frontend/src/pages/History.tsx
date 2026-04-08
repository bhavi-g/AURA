import { useState, useCallback } from 'react';
import { Search, Clock, ExternalLink, RefreshCw, FileSearch, MapPin } from 'lucide-react';
import { api } from '../api';
import RiskGauge from '../components/RiskGauge';
import SeverityBadge from '../components/SeverityBadge';
import Spinner from '../components/Spinner';
import ErrorBanner from '../components/ErrorBanner';
import type { AuditReport } from '../types';
import { severityFromLevel, ruleDisplayName } from '../utils';

export default function History() {
    const [jobId, setJobId] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [report, setReport] = useState<AuditReport | null>(null);

    const handleLookup = useCallback(async () => {
        if (!jobId.trim()) return;
        setLoading(true);
        setError(null);
        setReport(null);
        try {
            const res = await api.report(jobId.trim());
            setReport(res);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to fetch report');
        } finally {
            setLoading(false);
        }
    }, [jobId]);

    return (
        <div className="min-h-screen">
            {/* Hero */}
            <section className="relative overflow-hidden bg-bg-dark text-white">
                <div className="absolute inset-0 opacity-[0.03]" style={{
                    backgroundImage: 'radial-gradient(circle at 1px 1px, white 1px, transparent 0)',
                    backgroundSize: '40px 40px'
                }} />
                <div className="relative section-inner py-24 lg:py-32 text-center">
                    <p className="text-[13px] font-medium uppercase tracking-[0.2em] text-warm mb-4 animate-fade-up">
                        Audit Reports
                    </p>
                    <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-5 animate-fade-up delay-100">
                        History.
                    </h1>
                    <p className="text-lg md:text-xl text-white/50 max-w-lg mx-auto leading-relaxed animate-fade-up delay-200">
                        Look up past audit results by job ID and review findings.
                    </p>
                </div>
            </section>

            {/* Search */}
            <section className="section-full bg-white">
                <div className="max-w-2xl mx-auto px-8 animate-fade-up delay-300">
                    <label className="text-[13px] font-medium uppercase tracking-[0.15em] text-text-muted mb-4 block text-center">
                        Enter Job ID
                    </label>
                    <div className="flex gap-3">
                        <div className="relative flex-1">
                            <Search className="absolute left-5 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                            <input
                                type="text"
                                value={jobId}
                                onChange={(e) => setJobId(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleLookup()}
                                className="w-full bg-bg-primary border border-border rounded-full pl-12 pr-6 py-3.5 text-sm text-text-primary focus:outline-none focus:border-text-muted focus:shadow-lg transition-all duration-300 code-font"
                                placeholder="e.g. audit_abc123..."
                            />
                        </div>
                        <button
                            onClick={handleLookup}
                            disabled={loading || !jobId.trim()}
                            className="flex items-center gap-2 px-7 py-3.5 bg-bg-dark hover:bg-black text-white rounded-full text-sm font-semibold transition-all duration-300 disabled:opacity-30 disabled:cursor-not-allowed hover:scale-105 hover:shadow-lg active:scale-100"
                        >
                            <ExternalLink className="w-4 h-4" />
                            Lookup
                        </button>
                    </div>
                </div>
            </section>

            {loading && (
                <section className="section-full bg-bg-primary">
                    <Spinner label="Fetching audit report..." />
                </section>
            )}

            {error && (
                <section className="py-8">
                    <div className="max-w-3xl mx-auto px-8">
                        <ErrorBanner message={error} onRetry={handleLookup} />
                    </div>
                </section>
            )}

            {/* Report */}
            {report && (
                <>
                    {/* Status Banner */}
                    <section className="py-6 border-t border-border bg-white">
                        <div className="max-w-4xl mx-auto px-8 animate-fade-up">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <Clock className="w-5 h-5 text-text-muted" />
                                    <div>
                                        <p className="text-sm font-semibold text-text-primary">Audit Status</p>
                                        <p className="text-xs text-text-muted code-font mt-0.5">{jobId}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <span className={`inline-flex items-center px-4 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wide ${report.status === 'ready' ? 'bg-success/10 text-success' :
                                            report.status === 'error' ? 'bg-danger/10 text-danger' :
                                                'bg-bg-elevated text-text-muted'
                                        }`}>
                                        {report.status}
                                    </span>
                                    {(report.status === 'queued' || report.status === 'running') && (
                                        <button onClick={handleLookup} className="p-2 text-text-muted hover:text-text-primary rounded-lg transition-colors" title="Refresh">
                                            <RefreshCw className="w-4 h-4" />
                                        </button>
                                    )}
                                </div>
                            </div>
                        </div>
                    </section>

                    {report.error && (
                        <section className="py-8">
                            <div className="max-w-3xl mx-auto px-8">
                                <ErrorBanner message={report.error} />
                            </div>
                        </section>
                    )}

                    {report.report && (
                        <>
                            {/* Score + Summary */}
                            <section className="section-full bg-bg-primary">
                                <div className="section-inner">
                                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-16 items-center">
                                        <div className="flex justify-center animate-scale-in">
                                            <RiskGauge score={report.report.details.score} size="lg" />
                                        </div>
                                        <div className="lg:col-span-2 animate-fade-up delay-200">
                                            <div className="grid grid-cols-2 gap-8">
                                                <div className="bg-white rounded-3xl p-8 border border-border text-center">
                                                    <p className="text-5xl font-bold text-text-primary tabular-nums">{report.report.details.n_findings}</p>
                                                    <p className="text-sm text-text-muted mt-2">Total Findings</p>
                                                </div>
                                                <div className="bg-white rounded-3xl p-8 border border-border text-center">
                                                    <p className={`text-5xl font-bold tabular-nums ${report.report.summary.ok ? 'text-success' : 'text-danger'}`}>
                                                        {report.report.summary.ok ? 'PASS' : 'FAIL'}
                                                    </p>
                                                    <p className="text-sm text-text-muted mt-2">Verdict</p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </section>

                            {/* Findings */}
                            {report.report.details.reports.length > 0 && (
                                <section className="section-full bg-white">
                                    <div className="section-inner">
                                        <div className="text-center mb-16">
                                            <p className="text-[13px] font-medium uppercase tracking-[0.15em] text-text-muted mb-3 animate-fade-up">Details</p>
                                            <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-text-primary animate-fade-up delay-100">
                                                All findings.
                                            </h2>
                                        </div>
                                        <div className="max-w-4xl mx-auto space-y-4">
                                            {report.report.details.reports.map((f, i) => {
                                                const severity = severityFromLevel(f.level);
                                                return (
                                                    <div
                                                        key={`${f.ruleId}-${i}`}
                                                        className="bg-bg-primary rounded-2xl border border-border p-6 md:p-8 hover:shadow-lg hover:border-border-light transition-all duration-500 animate-fade-up"
                                                        style={{ animationDelay: `${i * 80}ms` }}
                                                    >
                                                        <div className="flex items-start justify-between gap-4 mb-3">
                                                            <div>
                                                                <div className="flex items-center gap-3 mb-1">
                                                                    <h3 className="text-lg font-semibold text-text-primary">{ruleDisplayName(f.ruleId)}</h3>
                                                                    <SeverityBadge severity={severity} />
                                                                </div>
                                                                <span className="text-xs text-text-muted code-font">{f.ruleId}</span>
                                                            </div>
                                                            <span className="text-2xl font-bold tabular-nums">{(f.score * 100).toFixed(0)}</span>
                                                        </div>
                                                        <p className="text-[15px] text-text-secondary leading-relaxed mb-4">{f.message}</p>
                                                        <div className="flex items-center gap-5 text-sm text-text-muted">
                                                            <span className="inline-flex items-center gap-1.5"><FileSearch className="w-4 h-4" />{f.location.file}</span>
                                                            <span className="inline-flex items-center gap-1.5"><MapPin className="w-4 h-4" />Line {f.location.startLine}</span>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                </section>
                            )}
                        </>
                    )}
                </>
            )}

            {/* Empty State */}
            {!report && !loading && !error && (
                <section className="py-32 text-center animate-fade-up delay-400">
                    <Clock className="w-16 h-16 text-border mx-auto mb-6" />
                    <p className="text-lg text-text-muted">Enter a job ID to view audit results</p>
                    <p className="text-sm text-text-muted/60 mt-2">Job IDs are returned when you submit an audit via the API</p>
                </section>
            )}
        </div>
    );
}
