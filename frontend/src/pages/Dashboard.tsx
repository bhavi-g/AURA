import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Shield, FileSearch, Sparkles, ArrowRight, AlertTriangle, FileCode2, MapPin } from 'lucide-react';
import RiskGauge from '../components/RiskGauge';
import SeverityBadge from '../components/SeverityBadge';
import SeverityChart from '../components/SeverityChart';
import type { Finding } from '../types';
import { severityFromLevel, ruleDisplayName } from '../utils';

const DEMO_FINDINGS: Finding[] = [
    {
        ruleId: 'reentrancy-eth',
        level: 'error',
        message: 'Reentrancy vulnerability detected in withdraw(). External call to msg.sender sends ETH before state update, allowing recursive calls to drain funds.',
        location: { file: 'contracts/Vault.sol', startLine: 42 },
        score: 0.95,
        tool: 'slither',
    },
    {
        ruleId: 'arbitrary-send-eth',
        level: 'error',
        message: 'Function transferFunds() sends ETH to an arbitrary user-controlled address without proper access control.',
        location: { file: 'contracts/Vault.sol', startLine: 67 },
        score: 0.88,
        tool: 'slither',
    },
    {
        ruleId: 'tx-origin',
        level: 'warning',
        message: 'Use of tx.origin for authorization in onlyOwner modifier. This can be exploited through phishing attacks.',
        location: { file: 'contracts/TxOrigin.sol', startLine: 15 },
        score: 0.72,
        tool: 'slither',
    },
    {
        ruleId: 'missing-zero-check',
        level: 'note',
        message: 'Missing zero-address validation for _newOwner parameter in transferOwnership().',
        location: { file: 'contracts/Vault.sol', startLine: 23 },
        score: 0.35,
        tool: 'slither',
    },
    {
        ruleId: 'solc-version',
        level: 'note',
        message: 'Solidity version 0.8.0 contains known compiler bugs. Consider upgrading to 0.8.19 or later.',
        location: { file: 'contracts/Vault.sol', startLine: 1 },
        score: 0.15,
        tool: 'slither',
    },
];

export default function Dashboard() {
    const [score] = useState(72);
    const [findings] = useState<Finding[]>(DEMO_FINDINGS);

    const criticalCount = findings.filter((f) => f.level === 'error').length;

    return (
        <div className="min-h-screen">
            {/* ─── HERO ─── */}
            <section className="relative overflow-hidden bg-bg-dark text-white">
                <div className="absolute inset-0 opacity-[0.03]" style={{
                    backgroundImage: 'radial-gradient(circle at 1px 1px, white 1px, transparent 0)',
                    backgroundSize: '40px 40px'
                }} />
                <div className="relative section-inner py-24 lg:py-36 text-center">
                    <p className="text-[13px] font-medium uppercase tracking-[0.2em] text-warm mb-6 animate-fade-up">
                        Smart Contract Security
                    </p>
                    <h1 className="text-5xl md:text-7xl lg:text-[84px] font-bold tracking-tight leading-[1.05] mb-6 animate-fade-up delay-100">
                        Security at a<br />
                        <span className="text-warm">glance.</span>
                    </h1>
                    <p className="text-lg md:text-xl text-white/50 max-w-xl mx-auto leading-relaxed animate-fade-up delay-200">
                        AURA continuously monitors your smart contracts for vulnerabilities, from reentrancy to access control flaws.
                    </p>

                    {/* Hero Stats */}
                    <div className="flex items-center justify-center gap-16 mt-16 animate-fade-up delay-300">
                        <div>
                            <p className="text-5xl md:text-6xl font-bold tabular-nums">{findings.length}</p>
                            <p className="text-sm text-white/40 mt-2">Findings</p>
                        </div>
                        <div className="w-px h-16 bg-white/10" />
                        <div>
                            <p className="text-5xl md:text-6xl font-bold tabular-nums text-severity-critical">{criticalCount}</p>
                            <p className="text-sm text-white/40 mt-2">Critical</p>
                        </div>
                        <div className="w-px h-16 bg-white/10" />
                        <div>
                            <p className="text-5xl md:text-6xl font-bold tabular-nums">{score}</p>
                            <p className="text-sm text-white/40 mt-2">Risk Score</p>
                        </div>
                    </div>
                </div>
            </section>

            {/* ─── RISK GAUGE + BREAKDOWN ─── */}
            <section className="section-full bg-white">
                <div className="section-inner">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-20 items-center">
                        {/* Gauge */}
                        <div className="flex justify-center animate-fade-up">
                            <div className="relative">
                                <RiskGauge score={score} size="lg" />
                                <div className="absolute -z-10 w-72 h-72 rounded-full bg-severity-critical/5 blur-3xl top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
                            </div>
                        </div>

                        {/* Breakdown */}
                        <div className="animate-fade-up delay-200">
                            <p className="text-[13px] font-medium uppercase tracking-[0.15em] text-text-muted mb-3">Analysis</p>
                            <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-text-primary mb-4">
                                Severity<br />Breakdown.
                            </h2>
                            <p className="text-lg text-text-muted leading-relaxed mb-10 max-w-md">
                                Understand the distribution of vulnerabilities across severity levels in your codebase.
                            </p>
                            <div className="max-w-sm">
                                <SeverityChart findings={findings} />
                            </div>
                            <div className="flex gap-6 mt-6">
                                {[
                                    { label: 'Critical', color: '#c0392b' },
                                    { label: 'Medium', color: '#e67e22' },
                                    { label: 'Low', color: '#2980b9' },
                                ].map((item) => (
                                    <div key={item.label} className="flex items-center gap-2 text-sm text-text-muted">
                                        <span className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                                        {item.label}
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* ─── FINDINGS ─── */}
            <section className="section-full bg-bg-primary">
                <div className="section-inner">
                    <div className="text-center mb-16">
                        <p className="text-[13px] font-medium uppercase tracking-[0.15em] text-text-muted mb-3 animate-fade-up">Detected Issues</p>
                        <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-text-primary animate-fade-up delay-100">
                            Every vulnerability,<br />accounted for.
                        </h2>
                    </div>

                    <div className="space-y-4 max-w-4xl mx-auto">
                        {findings.map((f, i) => {
                            const severity = severityFromLevel(f.level);
                            return (
                                <div
                                    key={f.ruleId}
                                    className="group bg-white rounded-2xl border border-border p-6 md:p-8 hover:shadow-lg hover:border-border-light transition-all duration-500 animate-fade-up cursor-default"
                                    style={{ animationDelay: `${i * 100}ms` }}
                                >
                                    <div className="flex items-start justify-between gap-4 mb-4">
                                        <div className="flex-1">
                                            <div className="flex items-center gap-3 mb-1">
                                                <h3 className="text-lg font-semibold text-text-primary group-hover:text-accent transition-colors duration-300">
                                                    {ruleDisplayName(f.ruleId)}
                                                </h3>
                                                <SeverityBadge severity={severity} />
                                            </div>
                                            <span className="text-xs text-text-muted code-font">{f.ruleId}</span>
                                        </div>
                                        <span className="text-2xl font-bold text-text-primary tabular-nums">
                                            {(f.score * 100).toFixed(0)}
                                        </span>
                                    </div>

                                    <p className="text-[15px] text-text-secondary leading-relaxed mb-5">
                                        {f.message}
                                    </p>

                                    <div className="flex items-center gap-5 text-sm text-text-muted">
                                        <span className="inline-flex items-center gap-1.5">
                                            <FileCode2 className="w-4 h-4" />
                                            {f.location.file}
                                        </span>
                                        <span className="inline-flex items-center gap-1.5">
                                            <MapPin className="w-4 h-4" />
                                            Line {f.location.startLine}
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </section>

            {/* ─── CTA CARDS ─── */}
            <section className="section-full bg-white">
                <div className="section-inner">
                    <div className="text-center mb-16">
                        <p className="text-[13px] font-medium uppercase tracking-[0.15em] text-text-muted mb-3 animate-fade-up">Next Steps</p>
                        <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-text-primary animate-fade-up delay-100">
                            Go deeper.
                        </h2>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
                        {[
                            {
                                icon: <FileSearch className="w-7 h-7" />,
                                title: 'Analyze',
                                desc: 'Run a deep security scan on any Solidity contract with multiple detectors.',
                                href: '/analyze',
                                bg: 'bg-bg-dark',
                                text: 'text-white',
                                descColor: 'text-white/50',
                            },
                            {
                                icon: <Sparkles className="w-7 h-7" />,
                                title: 'Explain',
                                desc: 'Get AI-powered explanations and remediation suggestions for every finding.',
                                href: '/explain',
                                bg: 'bg-accent-bg',
                                text: 'text-text-primary',
                                descColor: 'text-text-muted',
                            },
                            {
                                icon: <AlertTriangle className="w-7 h-7" />,
                                title: 'History',
                                desc: 'Look up past audit results by job ID and track security improvements.',
                                href: '/history',
                                bg: 'bg-bg-elevated',
                                text: 'text-text-primary',
                                descColor: 'text-text-muted',
                            },
                        ].map((card, i) => (
                            <Link
                                key={card.title}
                                to={card.href}
                                className={`group relative ${card.bg} rounded-3xl p-8 md:p-10 overflow-hidden transition-transform duration-500 hover:scale-[1.02] animate-fade-up`}
                                style={{ animationDelay: `${i * 120}ms` }}
                            >
                                <div className={`${card.text} mb-6 opacity-80`}>{card.icon}</div>
                                <h3 className={`text-2xl font-bold ${card.text} mb-3`}>{card.title}</h3>
                                <p className={`text-[15px] ${card.descColor} leading-relaxed mb-8`}>{card.desc}</p>
                                <div className={`inline-flex items-center gap-2 text-sm font-medium ${card.text} opacity-60 group-hover:opacity-100 group-hover:gap-3 transition-all duration-300`}>
                                    Learn more <ArrowRight className="w-4 h-4" />
                                </div>
                            </Link>
                        ))}
                    </div>
                </div>
            </section>

            {/* ─── FOOTER ─── */}
            <footer className="py-12 text-center border-t border-border">
                <div className="flex items-center justify-center gap-2 mb-3">
                    <Shield className="w-4 h-4 text-text-muted" />
                    <span className="text-sm font-semibold text-text-primary">AURA</span>
                </div>
                <p className="text-xs text-text-muted">
                    Automated Understanding & Remediation for Audits
                </p>
            </footer>
        </div>
    );
}
