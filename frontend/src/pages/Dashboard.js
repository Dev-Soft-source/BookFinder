import { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import Sidebar from '@/components/Sidebar';
import Overview from '@/components/Overview';
import ISBNManager from '@/components/ISBNManager';
import FiltersManager from '@/components/FiltersManager';
import ProfitableFinds from '@/components/ProfitableFinds';
import Logs from '@/components/Logs';
import Settings from '@/components/Settings';

export default function Dashboard({ onLogout }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <Sidebar isOpen={sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)} onLogout={onLogout} />
      <main className={`flex-1 overflow-y-auto transition-all duration-300 bg-[#ffebcd] ${sidebarOpen ? 'ml-64' : 'ml-0'}`}>
        <div className="p-6 max-w-7xl mx-auto">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/isbns" element={<ISBNManager />} />
            <Route path="/filters" element={<FiltersManager />} />
            <Route path="/profitable" element={<ProfitableFinds />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}
