import { useState, useCallback } from 'react';
import { Sparkles, Send, Brain, FileCode2 } from 'lucide-react';
import { api } from '../api';
import SeverityBadge from '../components/SeverityBadge';
import Spinner from '../components/Spinner';
import ErrorBanner from '../components/ErrorBanner';
import type { ExplainResponse, ExplainLLMResponse } from '../types';
import type { Severity } from '../types';

export default function Explain() {
    const [contractPath, setContractPath] = useState('contracts/Vault.sol');
    const [mode, setMode] = useState<'explain' | 'llm'>('explain');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [explainResult, setExplainResult] = useState<ExplainResponse | null>(null);
    const [llmResult, setLlmResult] = useState<ExplainLLMResponse | null>(null);

    const handleSubmit = useCallback(async () => {
        setLoading(true);
        setError(null);
        setExplainResult(null);
        setLlmResult(null);
        try {
            if (mode === 'explain') {
                const res = await api.explain(contractPath);
                setExplainResult(res);
            } else {
                const res = await api.explainLLM(contractPath);
                setLlmResult(res);
            }
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Request failed');
        } finally {
            setLoading(false);
        }
    }, [contractPath, mode]);

    return (
        <div className="min-h-screen">
            {/* Hero */}
            <section className="relative overflow-hidden bg-accent-bg border-b border-border">
                <div className="absolute inset-0 opacity-[0.02]" style={{
                    backgroundImage: 'radial-gradient(circle at 1px 1px, var(--color-accent) 1px, transparent 0)',
                    backgroundSize: '48px 48px'
                }} />
                <div className="relative section-inner py-24 lg:py-32 text-center">
                    <p className="text-[13px] font-medium uppercase tracking-[0.2em] text-accent mb-4 animate-fade-up">
                        AI-Powered Insights
                    </p>
                    <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-text-primary mb-5 animate-fade-up delay-100">
                        Explain.
                    </h1>
                    <p className="text-lg md:text-xl text-text-muted max-w-lg mx-auto leading-relaxed animate-fade-up delay-200">
                        Get human-readable explanations and AI-powered fix suggestions for every vulnerability.
                    </p>
                </div>
            </section>

            {/* Input */}
            <section className="section-full bg-white">
                <div className="max-w-2xl mx-auto px-8 animate-fade-up delay-300">
                    {/* Mode Toggle */}
                    <div className="flex items-center gap-1 p-1 bg-bg-elevated rounded-full w-fit mx-auto mb-10">
                        <button
                            onClick={() => setMode('explain')}
                            className={`flex items-center gap-2 px-5 py-2 rounded-full text-sm font-medium transition-all duration-300 ${mode === 'explain' ? 'bg-bg-dark text-white shadow-sm' : 'text-text-muted hover:text-text-primary'
                                }`}
                        >
                            <FileCode2 className="w-4 h-4" />
                            Summary
                        </button>
                        <button
                            onClick={() => setMode('llm')}
                            className={`flex items-center gap-2 px-5 py-2 rounded-full text-sm font-medium transition-all duration-300 ${mode === 'llm' ? 'bg-bg-dark text-white shadow-sm' : 'text-text-muted hover:text-text-primary'
                                }`}
                        >
                            <Brain className="w-4 h-4" />
                            AI Deep Dive
                        </button>
                    </div>

                    {/* Search Bar */}
                    <div className="flex gap-3">
                        <input
                            type="text"
                            value={contractPath}
                            onChange={(e) => setContractPath(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                            className="flex-1 bg-bg-primary border border-border rounded-full px-6 py-3.5 text-sm text-text-primary focus:outline-none focus:border-text-muted focus:shadow-lg transition-all duration-300 code-font"
                            placeholder="contracts/MyContract.sol"
                        />
                        <button
                            onClick={handleSubmit}
                            disabled={loading || !contractPath}
                            className="flex items-center gap-2 px-7 py-3.5 bg-bg-dark hover:bg-black text-white rounded-full text-sm font-semibold transition-all duration-300 disabled:opacity-30 disabled:cursor-not-allowed hover:scale-105 hover:shadow-lg active:scale-100"
                        >
                            {mode === 'llm' ? <Sparkles className="w-4 h-4" /> : <Send className="w-4 h-4" />}
                            {mode === 'llm' ? 'Ask AI' : 'Explain'}
                        </button>
                    </div>

                    {mode === 'llm' && (
                        <p className="text-xs text-text-muted mt-4 text-center flex items-center justify-center gap-1.5">
                            <Brain className="w-3.5 h-3.5" />
                            Uses LLM to generate detailed explanations with fix suggestions
                        </p>
                    )}
                </div>
            </section>

            {loading && (
                <section className="section-full bg-bg-primary">
                    <Spinner label={mode === 'llm' ? 'AI is thinking...' : 'Generating explanation...'} />
                </section>
            )}

            {error && (
                <section className="py-8">
                    <div className="max-w-3xl mx-auto px-8">
                        <ErrorBanner message={error} onRetry={handleSubmit} />
                    </div>
                </section>
            )}

            {/* Structured Explain Result */}
            {explainResult && (
                <>
                    {/* Summary */}
                    <section className="section-full bg-bg-primary border-t border-border">
                        <div className="section-inner">
                            <div className="grid grid-cols-1 lg:grid-cols-3 gap-12 items-start">
                                <div className="lg:col-span-2 animate-fade-up">
                                    <p className="text-[13px] font-medium uppercase tracking-[0.15em] text-text-muted mb-3">Summary</p>
                                    <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-text-primary mb-6">
                                        Analysis Complete.
                                    </h2>
                                    <p className="text-[15px] text-text-secondary leading-[1.8] whitespace-pre-wrap">
                                        {explainResult.summary}
                                    </p>
                                </div>
                                <div className="flex flex-col items-center gap-6 animate-fade-up delay-200">
                                    <div className="bg-white rounded-3xl p-8 border border-border text-center w-full">
                                        <p className="text-6xl font-bold text-text-primary tabular-nums">{explainResult.score}</p>
                                        <p className="text-sm text-text-muted mt-2">Risk Score</p>
                                    </div>
                                    <div className="bg-white rounded-3xl p-8 border border-border text-center w-full">
                                        <p className="text-4xl font-bold text-text-primary tabular-nums">{explainResult.n_findings}</p>
                                        <p className="text-sm text-text-muted mt-2">Findings</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* Top Findings */}
                    {explainResult.top_findings.length > 0 && (
                        <section className="section-full bg-white">
                            <div className="section-inner">
                                <div className="text-center mb-16">
                                    <p className="text-[13px] font-medium uppercase tracking-[0.15em] text-text-muted mb-3 animate-fade-up">Details</p>
                                    <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-text-primary animate-fade-up delay-100">
                                        Top findings.
                                    </h2>
                                </div>

                                <div className="max-w-4xl mx-auto space-y-4">
                                    {explainResult.top_findings.map((f, i) => (
                                        <div
                                            key={f.rule_id}
                                            className="bg-bg-primary rounded-2xl p-6 md:p-8 border border-border hover:shadow-lg hover:border-border-light transition-all duration-500 animate-fade-up"
                                            style={{ animationDelay: `${i * 100}ms` }}
                                        >
                                            <div className="flex items-start justify-between gap-4 mb-3">
                                                <div>
                                                    <div className="flex items-center gap-3 mb-1">
                                                        <h3 className="text-lg font-semibold text-text-primary">{f.title}</h3>
                                                        <SeverityBadge severity={f.severity.toUpperCase() as Severity} />
                                                    </div>
                                                    <span className="text-xs text-text-muted code-font">{f.rule_id}</span>
                                                </div>
                                                <span className="text-2xl font-bold tabular-nums text-text-primary">
                                                    {(f.score * 100).toFixed(0)}
                                                </span>
                                            </div>
                                            <p className="text-[15px] text-text-secondary leading-relaxed">{f.description}</p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </section>
                    )}
                </>
            )}

            {/* LLM Result */}
            {llmResult && (
                <section className="section-full bg-white border-t border-border">
                    <div className="max-w-3xl mx-auto px-8 animate-fade-up">
                        <div className="flex items-center gap-3 mb-8">
                            <div className="w-10 h-10 rounded-2xl bg-accent-bg flex items-center justify-center">
                                <Sparkles className="w-5 h-5 text-accent" />
                            </div>
                            <div>
                                <h2 className="text-xl font-bold text-text-primary">AI Explanation</h2>
                                <p className="text-xs text-text-muted">Generated by language model</p>
                            </div>
                        </div>
                        <div className="text-[15px] text-text-secondary leading-[1.9] whitespace-pre-wrap">
                            {llmResult.explanation}
                        </div>
                    </div>
                </section>
            )}
        </div>
    );
}
