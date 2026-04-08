import { Loader2 } from 'lucide-react';

interface Props {
    label?: string;
}

export default function Spinner({ label }: Props) {
    return (
        <div className="flex flex-col items-center justify-center gap-5 py-24">
            <Loader2 className="w-10 h-10 text-text-muted/40 animate-spin" />
            {label && <p className="text-[15px] text-text-muted">{label}</p>}
        </div>
    );
}
