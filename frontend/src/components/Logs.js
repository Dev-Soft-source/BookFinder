import { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '@/App';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { AlertCircle, CheckCircle, Info } from 'lucide-react';
import { RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function Logs() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 3000000);
    return () => clearInterval(interval);
  }, []);

  const fetchLogs = async () => {
    try {
      const response = await axios.get(`${API}/logs`);
      setLogs(response.data);
    } catch (error) {
      toast.error('Failed to fetch logs');
    } finally {
      setLoading(false);
    }
  };

  const resetAllLogs = async () => {
    if (!window.confirm("Are you sure you want to delete all logs?")) return;

    try {
      await axios.delete(`${API}/logs/reset`); // ← Backend endpoint
      toast.success("All logs deleted successfully");
      setLogs([]);
    } catch (error) {
      toast.error("Failed to reset logs");
    }
  };

  const getLogIcon = (type) => {
    switch (type) {
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      default:
        return <Info className="w-5 h-5 text-blue-500" />;
    }
  };

  const getLogBadge = (type) => {
    const colors = {
      error: 'bg-red-100 text-red-800',
      success: 'bg-green-100 text-green-800',
      info: 'bg-blue-100 text-blue-800',
    };
    return <Badge className={colors[type] || colors.info}>{type}</Badge>;
  };

  if (loading) {
    return (
      <div className="fixed inset-0 flex justify-center items-center bg-white/70 backdrop-blur-sm z-50">
        <div className="relative w-16 h-16">
          {/* Outer slow spinner */}
          <div className="absolute inset-0 border-4 border-cyan-600 border-t-transparent rounded-full animate-spin [animation-duration:1.4s]"></div>

          {/* Inner faster spinner */}
          <div className="absolute inset-3 border-4 border-cyan-400 border-b-transparent rounded-full animate-spin [animation-duration:0.9s]"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="logs-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-gray-800">System Logs</h1>
          <p className="text-gray-600 mt-2">Monitor scraper activity and errors</p>
        </div>

        <Button
          onClick={resetAllLogs}
          variant="outline"
          className="flex items-center space-x-2  bg-cyan-600 hover:bg-cyan-800 hover:text-red-200 text-white"
          data-testid="reset-button"
        >
          <RotateCcw className="w-4 h-4" />
          <span>Reset</span>
        </Button>
      </div>

      <Card className="shadow-lg bg-[#fff8dc]">
        <CardHeader>
          <CardTitle>Recent Activity ({logs.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 max-h-[600px] overflow-y-auto">
            {logs.length === 0 ? (
              <p className="text-center text-gray-500 py-8">No logs yet</p>
            ) : (
              logs.map((log) => (
                <div
                  key={log.id}
                  className="flex items-start space-x-3 p-4 bg-[#f8e5ce] rounded-lg hover:bg-[#e6cfb4] transition-colors"
                  data-testid="log-item"
                >
                  <div className="flex-shrink-0 mt-1">
                    {getLogIcon(log.log_type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      {getLogBadge(log.log_type)}
                      <span className="text-xs text-gray-500">
                        {new Date(log.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <p className="text-sm text-gray-700">{log.message}</p>
                    {log.isbn && (
                      <p className="text-xs text-gray-500 mt-1">ISBN: {log.isbn}</p>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
