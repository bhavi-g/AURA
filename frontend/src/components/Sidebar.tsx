import { NavLink } from 'react-router-dom';
import { Shield, BarChart3, FileSearch, History, Sparkles } from 'lucide-react';

const links = [
    { to: '/', icon: BarChart3, label: 'Dashboard' },
    { to: '/analyze', icon: FileSearch, label: 'Analyze' },
    { to: '/explain', icon: Sparkles, label: 'Explain' },
    { to: '/history', icon: History, label: 'History' },
];

export default function Sidebar() {
    return (
        <header className="fixed top-0 left-0 right-0 z-50 glass-panel">
            <div className="max-w-[1400px] mx-auto px-8 flex items-center justify-between h-14">
                <NavLink to="/" className="flex items-center gap-2.5 group">
                    <div className="w-7 h-7 rounded-md bg-bg-dark flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                        <Shield className="w-4 h-4 text-white" />
                    </div>
                    <span className="text-base font-semibold tracking-tight text-text-primary">
                        AURA
                    </span>
                </NavLink>

                <nav className="flex items-center gap-0.5">
                    {links.map(({ to, icon: Icon, label }) => (
                        <NavLink
                            key={to}
                            to={to}
                            className={({ isActive }) =>
                                `flex items-center gap-1.5 px-4 py-1.5 rounded-full text-[13px] font-medium transition-all duration-300 ${isActive
                                    ? 'bg-bg-dark text-white shadow-sm'
                                    : 'text-text-muted hover:text-text-primary'
                                }`
                            }
                        >
                            <Icon className="w-3.5 h-3.5" />
                            {label}
                        </NavLink>
                    ))}
                </nav>

                <div className="flex items-center gap-2 text-[11px] font-medium text-text-muted uppercase tracking-widest">
                    <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse-soft" />
                    Live
                </div>
            </div>
        </header>
    );
}
