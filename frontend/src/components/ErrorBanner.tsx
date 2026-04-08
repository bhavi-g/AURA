import { AlertTriangle } from 'lucide-react';

interface Props {
    message: string;
    onRetry?: () => void;
}

export default function ErrorBanner({ message, onRetry }: Props) {
    return (
        <div className="flex items-center gap-3 bg-danger/10 border border-danger/25 rounded-xl px-5 py-4">
            <AlertTriangle className="w-5 h-5 text-danger shrink-0" />
            <p className="text-sm text-danger flex-1">{message}</p>
            {onRetry && (
                <button
                    onClick={onRetry}
                    className="text-xs font-medium text-danger hover:text-danger-light underline underline-offset-2 shrink-0"
                >
                    Retry
                </button>
            )}
        </div>
    );
}
