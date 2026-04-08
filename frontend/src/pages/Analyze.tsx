import { useState, useCallback } from 'react';
import { Play, Upload, FileCode2, ChevronDown, FileSearch, MapPin } from 'lucide-react';
import { api } from '../api';
import RiskGauge from '../components/RiskGauge';
import SeverityBadge from '../components/SeverityBadge';
import SeverityChart from '../components/SeverityChart';
import Spinner from '../components/Spinner';
import ErrorBanner from '../components/ErrorBanner';
import type { AnalyzeResponse } from '../types';
import { severityFromLevel, ruleDisplayName } from '../utils';

const SAMPLE_CONTRACT = `// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Vault {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() external {
        uint256 amount = balances[msg.sender];
        require(amount > 0, "No balance");

        // Vulnerable: sends ETH before updating state
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");

        balances[msg.sender] = 0;
    }
}`;

export default function Analyze() {
  const [mode, setMode] = useState<'path' | 'paste'>('paste');
  const [contractPath, setContractPath] = useState('');
  const [source, setSource] = useState(SAMPLE_CONTRACT);
  const [fullAnalysis, setFullAnalysis] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);

  const handleAnalyze = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const path = mode === 'path' ? contractPath : '/tmp/aura_paste.sol';
      const res = await api.analyze(path, fullAnalysis);
      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setLoading(false);
    }
  }, [mode, contractPath, fullAnalysis]);

  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section className="section-full bg-white border-b border-border">
        <div className="section-inner text-center">
          <p className="text-[13px] font-medium uppercase tracking-[0.2em] text-text-muted mb-4 animate-fade-up">
            Security Analysis
          </p>
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-text-primary mb-5 animate-fade-up delay-100">
            Analyze.
          </h1>
          <p className="text-lg md:text-xl text-text-muted max-w-lg mx-auto leading-relaxed animate-fade-up delay-200">
            Paste your Solidity code or point to a file. AURA runs a comprehensive security scan in seconds.
          </p>
        </div>
      </section>

      {/* Input Section */}
      <section className="section-full bg-bg-primary">
        <div className="max-w-3xl mx-auto px-8 animate-fade-up delay-300">
          {/* Mode Toggle */}
          <div className="flex items-center gap-1 p-1 bg-bg-elevated rounded-full w-fit mx-auto mb-10">
            <button
              onClick={() => setMode('paste')}
              className={`flex items-center gap-2 px-5 py-2 rounded-full text-sm font-medium transition-all duration-300 ${mode === 'paste' ? 'bg-bg-dark text-white shadow-sm' : 'text-text-muted hover:text-text-primary'
                }`}
            >
              <FileCode2 className="w-4 h-4" />
              Paste Source
            </button>
            <button
              onClick={() => setMode('path')}
              className={`flex items-center gap-2 px-5 py-2 rounded-full text-sm font-medium transition-all duration-300 ${mode === 'path' ? 'bg-bg-dark text-white shadow-sm' : 'text-text-muted hover:text-text-primary'
                }`}
            >
              <Upload className="w-4 h-4" />
              File Path
            </button>
          </div>

          {/* Input */}
          {mode === 'paste' ? (
            <div className="relative">
              <textarea
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="w-full h-96 bg-white border border-border rounded-2xl p-6 text-sm text-text-primary code-font resize-none focus:outline-none focus:border-text-muted focus:shadow-lg transition-all duration-300"
                placeholder="Paste your Solidity contract here..."
                spellCheck={false}
              />
              <span className="absolute bottom-4 right-5 text-xs text-text-muted bg-white/80 px-2 py-0.5 rounded">
                {source.split('\n').length} lines
              </span>
            </div>
          ) : (
            <input
              type="text"
              value={contractPath}
              onChange={(e) => setContractPath(e.target.value)}
              className="w-full bg-white border border-border rounded-2xl px-6 py-4 text-base text-text-primary focus:outline-none focus:border-text-muted focus:shadow-lg transition-all duration-300 code-font"
              placeholder="contracts/MyContract.sol"
            />
          )}

          {/* Options & Run */}
          <div className="flex items-center justify-between mt-8">
            <label className="flex items-center gap-3 cursor-pointer group">
              <div
                onClick={() => setFullAnalysis(!fullAnalysis)}
                className={`w-10 h-6 rounded-full transition-colors duration-300 relative cursor-pointer ${fullAnalysis ? 'bg-bg-dark' : 'bg-border'
                  }`}
              >
                <div className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-300 ${fullAnalysis ? 'translate-x-[18px]' : 'translate-x-1'
                  }`} />
              </div>
              <span className="text-sm text-text-secondary group-hover:text-text-primary transition-colors">
                Deep analysis
              </span>
              <ChevronDown className="w-3.5 h-3.5 text-text-muted" />
            </label>

            <button
              onClick={handleAnalyze}
              disabled={loading || (!contractPath && mode === 'path') || (!source && mode === 'paste')}
              className="flex items-center gap-2.5 px-8 py-3 bg-bg-dark hover:bg-black text-white rounded-full text-sm font-semibold transition-all duration-300 disabled:opacity-30 disabled:cursor-not-allowed hover:scale-105 hover:shadow-lg active:scale-100"
            >
              <Play className="w-4 h-4" />
              Run Analysis
            </button>
          </div>
        </div>
      </section>

      {/* Loading */}
      {loading && (
        <section className="section-full bg-white">
          <Spinner label="Scanning your contract for vulnerabilities..." />
        </section>
      )}

      {/* Error */}
      {error && (
        <section className="py-8">
          <div className="max-w-3xl mx-auto px-8">
            <ErrorBanner message={error} onRetry={handleAnalyze} />
          </div>
        </section>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Score Section */}
          <section className="section-full bg-white border-t border-border">
            <div className="section-inner">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-20 items-center">
                <div className="flex justify-center animate-scale-in">
                  <RiskGauge score={result.score} size="lg" />
                </div>
                <div className="animate-fade-up delay-200">
                  <p className="text-[13px] font-medium uppercase tracking-[0.15em] text-text-muted mb-3">Results</p>
                  <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-text-primary mb-4">
                    {result.n_findings} issue{result.n_findings !== 1 ? 's' : ''}<br />found.
                  </h2>
                  <p className="text-lg text-text-muted leading-relaxed mb-10 max-w-md">
                    Here's how vulnerabilities are distributed across severity levels.
                  </p>
                  <div className="max-w-sm">
                    <SeverityChart findings={result.reports} />
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Finding Cards */}
          <section className="section-full bg-bg-primary">
            <div className="max-w-4xl mx-auto px-8 space-y-4">
              {result.reports.map((f, i) => {
                const severity = severityFromLevel(f.level);
                return (
                  <div
                    key={`${f.ruleId}-${f.location.startLine}`}
                    className="bg-white rounded-2xl border border-border p-6 md:p-8 hover:shadow-lg hover:border-border-light transition-all duration-500 animate-fade-up"
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
          </section>
        </>
      )}
    </div>
  );
}
