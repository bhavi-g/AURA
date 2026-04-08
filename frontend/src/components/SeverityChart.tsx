import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import type { Finding } from '../types';
import { severityFromLevel, severityColor } from '../utils';
import type { Severity } from '../types';

interface Props {
    findings: Finding[];
}

export default function SeverityChart({ findings }: Props) {
    const counts: Record<Severity, number> = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 };
    findings.forEach((f) => {
        const s = severityFromLevel(f.level);
        counts[s]++;
    });

    const data = (Object.entries(counts) as [Severity, number][])
        .filter(([, v]) => v > 0)
        .map(([name, value]) => ({ name, value, color: severityColor(name) }));

    if (data.length === 0) {
        return (
            <div className="flex items-center justify-center h-48 text-text-muted text-sm">
                No findings to visualize
            </div>
        );
    }

    return (
        <ResponsiveContainer width="100%" height={240}>
            <PieChart>
                <Pie
                    data={data}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={95}
                    paddingAngle={4}
                    dataKey="value"
                    stroke="none"
                >
                    {data.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                    ))}
                </Pie>
                <Tooltip
                    contentStyle={{
                        background: '#ffffff',
                        border: '1px solid #e5e2dc',
                        borderRadius: '12px',
                        color: '#1d1d1f',
                        fontSize: '13px',
                        boxShadow: '0 8px 30px rgba(0,0,0,0.08)',
                        padding: '8px 14px',
                    }}
                />
            </PieChart>
        </ResponsiveContainer>
    );
}
