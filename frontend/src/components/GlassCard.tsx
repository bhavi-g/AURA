interface Props {
    children: React.ReactNode;
    className?: string;
}

export default function GlassCard({ children, className = '' }: Props) {
    return (
        <div className={`bg-white border border-border rounded-2xl shadow-sm ${className}`}>
            {children}
        </div>
    );
}
