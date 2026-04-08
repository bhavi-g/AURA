import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Analyze from './pages/Analyze';
import Explain from './pages/Explain';
import History from './pages/History';

export default function App() {
    return (
        <BrowserRouter>
            <div className="min-h-screen bg-bg-primary">
                <Sidebar />
                <main className="pt-14">
                    <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/analyze" element={<Analyze />} />
                        <Route path="/explain" element={<Explain />} />
                        <Route path="/history" element={<History />} />
                    </Routes>
                </main>
            </div>
        </BrowserRouter>
    );
}
