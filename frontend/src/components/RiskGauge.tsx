import { riskBand, riskLabel, riskColor, formatScore, riskBgClass } from '../utils';

interface Props {
    score: number;
    size?: 'sm' | 'lg';
}

export default function RiskGauge({ score, size = 'lg' }: Props) {
    const band = riskBand(score);
    const circumference = 2 * Math.PI * 54;
    const progress = (score / 100) * circumference;
    const strokeColor = {
        pass: '#27ae60',
        warning: '#e67e22',
        critical: '#c0392b',
        manual_review: '#d35400',
    }[band];

    if (size === 'sm') {
        return (
            <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border ${riskBgClass(band)}`}>
                <span className={`text-lg font-bold ${riskColor(band)}`}>{formatScore(score)}</span>
                <span className="text-xs text-text-secondary">{riskLabel(band)}</span>
            </div>
        );
    }

    return (
        <div className="flex flex-col items-center gap-5">
            <div className="relative w-52 h-52">
                <svg className="w-full h-full -rotate-90" viewBox="0 0 120 120">
                    <circle cx="60" cy="60" r="54" fill="none" stroke="#f0ede8" strokeWidth="6" />
                    <circle
                        cx="60" cy="60" r="54"
                        fill="none"
                        stroke={strokeColor}
                        strokeWidth="6"
                        strokeLinecap="round"
                        strokeDasharray={circumference}
                        strokeDashoffset={circumference - progress}
                        className="transition-all duration-[1.5s] ease-out"
                        style={{ filter: `drop-shadow(0 0 8px ${strokeColor}30)` }}
                    />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className={`text-5xl font-bold ${riskColor(band)} tabular-nums`}>{formatScore(score)}</span>
                    <span className="text-sm text-text-muted mt-1">/ 100</span>
                </div>
            </div>
            <span className={`text-sm font-semibold uppercase tracking-[0.15em] ${riskColor(band)}`}>
                {riskLabel(band)}
            </span>
        </div>
    );
}
