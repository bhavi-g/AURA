import { type ReactNode } from 'react';

interface Props {
    title: string;
    value: string | number;
    subtitle?: string;
    icon: ReactNode;
    color?: string;
    trend?: 'up' | 'down' | 'neutral';
}

export default function StatCard({ title, value, subtitle, icon, color = 'text-accent' }: Props) {
    return (
        <div className="bg-white border border-border rounded-xl p-5 hover:border-border-light transition-colors duration-200 shadow-sm">
            <div className="flex items-start justify-between mb-3">
                <span className="text-xs font-medium text-text-muted uppercase tracking-wider">{title}</span>
                <div className={`${color} opacity-50`}>{icon}</div>
            </div>
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
            {subtitle && <p className="text-xs text-text-muted mt-1">{subtitle}</p>}
        </div>
    );
}
