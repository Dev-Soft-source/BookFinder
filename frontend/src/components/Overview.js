import { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '@/App';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { BookOpen, Filter, TrendingUp, Clock, Play, StopCircleIcon } from 'lucide-react';
import { toast } from 'sonner';

export default function Overview() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [stopping, setStopping] = useState(false);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 25000);
    return () => clearInterval(interval);
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/stats`);
      if (response.data.running){
        setRunning(true);
        setStopping(false);
      }else
      {
        setRunning(false);
        setStopping(true);
      }
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const stopScraper = async () => {
    if (!running || stopping) return; // cannot stop if not running
    
    setStopping(true);

    try {
      const result = await axios.post(`${API}/scraper/stop`);
      toast.success(result.data.message || "Scraper stopped!");
      setRunning(false);
    } catch (error) {
      toast.error("Failed to stop scraper");
    } finally {
      setStopping(false);
    }
  };

  const runScraper = async () => {
    if (running) return;
    setRunning(true);
    try {
      const result = await axios.post(`${API}/scraper/run`);
      toast.success(result.data.message || 'Scraper run initiated');
      fetchStats(); // fetch latest stats immediately
    } catch (error) {
      toast.error('Failed to run scraper');
      setRunning(false);
    } finally {
      
    }
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

  const statCards = [
    {
      title: 'Total ISBNs',
      value: stats?.total_isbns || 0,
      icon: BookOpen,
      color: 'from-blue-500 to-blue-600',
      testId: 'stat-total-isbns'
    },
    {
      title: 'Checked Today',
      value: stats?.checked_today || 0,
      icon: Clock,
      color: 'from-purple-500 to-purple-600',
      testId: 'stat-checked-today'
    },
    {
      title: 'Profitable Finds',
      value: stats?.profitable_finds || 0,
      icon: TrendingUp,
      color: 'from-green-500 to-green-600',
      testId: 'stat-profitable-finds'
    },
  ];

  return (
    <div className="space-y-6" data-testid="overview-page">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold text-gray-800">Dashboard Overview</h1>
          <p className="text-gray-600 mt-2">Monitor your book arbitrage operations</p>
        </div>
        <div className="flex space-x-3">
          {/* Run Scraper */}
          <Button
            onClick={runScraper}
            disabled={running || !stopping}
            className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
            data-testid="run-scraper-button"
          >
            <Play className="w-4 h-4 mr-2" />
            {running ? 'Running...' : 'Run Scraper Now'}
          </Button>

          {/* Stop Scraper */}
          <Button
            onClick={stopScraper}
            disabled={!running || stopping}
            className="bg-gradient-to-r from-red-600 to-red-600 hover:from-red-700 hover:to-red-700"
            data-testid="stop-scraper-button"
          >
            <StopCircleIcon className="w-4 h-4 mr-2" />
            {stopping ? 'Stopping...' : 'Stop Scraper'}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {statCards.map((card) => {
          const Icon = card.icon;
          return (
            <Card key={card.title} className="overflow-hidden shadow-lg hover:shadow-xl transition-shadow" data-testid={card.testId}>
              <CardHeader className={`bg-gradient-to-r ${card.color} text-white pb-3`}>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg font-medium">{card.title}</CardTitle>
                  <Icon className="w-6 h-6 opacity-80" />
                </div>
              </CardHeader>
              <CardContent className="pt-6">
                <p className="text-4xl font-bold text-gray-800" data-testid={`${card.testId}-value`}>{card.value}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card className="shadow-lg">
        <CardHeader>
          <CardTitle>System Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex justify-between py-2 border-b">
            <span className="text-gray-600">Last Check:</span>
            <span className="font-medium" data-testid="last-check-time">
              {stats?.last_check ? new Date(stats.last_check).toLocaleString() : 'Never'}
            </span>
          </div>
          <div className="flex justify-between py-2 border-b">
            <span className="text-gray-600">Status:</span>
            <span className="font-medium text-green-600" data-testid="scraper-status">Active (24/7)</span>
          </div>
          <div className="flex justify-between py-2">
            <span className="text-gray-600">Check Interval:</span>
            <span className="font-medium">Every 24-48 hours per ISBN</span>
          </div>
        </CardContent>
      </Card>

      <Card className="shadow-lg bg-gradient-to-br from-blue-50 to-purple-50 border-blue-200">
        <CardHeader>
          <CardTitle className="text-blue-800">Quick Start Guide</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="space-y-2 text-gray-700">
            <li className="flex items-start">
              <span className="font-bold text-blue-600 mr-2">1.</span>
              <span>Upload your ISBN list in the <strong>ISBN List</strong> section</span>
            </li>
            <li className="flex items-start">
              <span className="font-bold text-blue-600 mr-2">2.</span>
              <span>Configure banned sellers, countries, or websites in <strong>Filters</strong></span>
            </li>
            <li className="flex items-start">
              <span className="font-bold text-blue-600 mr-2">3.</span>
              <span>Monitor profitable opportunities in <strong>Profitable Finds</strong></span>
            </li>
            <li className="flex items-start">
              <span className="font-bold text-blue-600 mr-2">4.</span>
              <span>Check <strong>Logs</strong> for scraper activity and errors</span>
            </li>
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
