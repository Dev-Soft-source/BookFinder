import { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { API } from '@/App';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Download, ExternalLink, TrendingUp, RotateCcw, ChevronLeft, ChevronRight } from 'lucide-react';

const PAGE_SIZE_OPTIONS = [5, 10, 25, 50];

export default function ProfitableFinds() {
  const [finds, setFinds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  useEffect(() => {
    fetchFinds();
    const interval = setInterval(fetchFinds, 6000000);
    return () => clearInterval(interval);
  }, []);

  const totalPages = Math.max(1, Math.ceil(finds.length / pageSize));
  const safePage = Math.min(currentPage, totalPages);

  const paginatedFinds = useMemo(() => {
    const start = (safePage - 1) * pageSize;
    return finds.slice(start, start + pageSize);
  }, [finds, safePage, pageSize]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  const fetchFinds = async () => {
    try {
      const response = await axios.get(`${API}/profitable`);
      setFinds(response.data);
    } catch (error) {
      toast.error('Failed to fetch profitable finds');
    } finally {
      setLoading(false);
    }
  };

  const resetFinds = async () => {
    if (!window.confirm("Are you sure you want to delete all profitable finds?")) return;

    try {
      await axios.delete(`${API}/profitable/reset`);
      toast.success("All profitable finds cleared");
      setFinds([]);
    } catch (error) {
      toast.error("Failed to reset finds");
    }
  };

  const exportCSV = async () => {
    try {
      const response = await axios.get(`${API}/export/csv`, {
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `profitable_finds_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success('CSV exported successfully');
    } catch (error) {
      toast.error('Failed to export CSV');
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

  return (
    <div className="space-y-6" data-testid="profitable-finds-page">
      <div className="flex justify-between items-center">
        <div className="flex justify-between items-center w-full">
          {/* Left: Page title */}
          <div>
            <h1 className="text-4xl font-bold text-gray-800">Profitable Finds</h1>
            <p className="text-gray-600 mt-2">Discovered arbitrage opportunities</p>
          </div>

          {/* Right: Buttons */}
          <div className="flex space-x-2 ml-auto">
            <Button
              onClick={resetFinds}
              variant="outline"
              className="flex items-center space-x-2  bg-cyan-600 hover:bg-cyan-800 hover:text-red-200 text-white"
              data-testid="reset-finds-button"
            >
              <RotateCcw className="w-5 h-5" />
              <span>Reset</span>
            </Button>

            <Button
              onClick={exportCSV}
              className="bg-slate-500 hover:bg-slate-700 hover:text-white text-white"
              variant="outline"
              data-testid="export-csv-button"
            >
              <Download className="w-4 h-4 mr-2" />
              Export CSV
            </Button>
          </div>
        </div>
      </div>

      {finds.length === 0 ? (
        <Card className="shadow-lg">
          <CardContent className="text-center py-12">
            <TrendingUp className="w-16 h-16 mx-auto text-gray-400 mb-4" />
            <p className="text-gray-500 text-lg">No profitable finds yet</p>
            <p className="text-gray-400 text-sm mt-2">The scraper will notify you when opportunities are found</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gray-200 bg-gray-50/80 px-4 py-3">
            <p className="text-sm text-gray-600">
              Showing <span className="font-medium text-gray-800">{finds.length}</span> find{finds.length !== 1 ? 's' : ''}
            </p>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <label className="flex items-center gap-2 text-gray-600">
                <span>Per page</span>
                <select
                  className="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-gray-800"
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setCurrentPage(1);
                  }}
                  data-testid="profitable-finds-page-size"
                >
                  {PAGE_SIZE_OPTIONS.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <span className="text-gray-500" data-testid="profitable-finds-page-info">
                Page {safePage} of {totalPages}
              </span>
            </div>
          </div>

          <div className="space-y-4">
          {paginatedFinds.map((find) => (
            <Card key={find.id} className="shadow-lg hover:shadow-xl transition-shadow" data-testid="profitable-find-item">
              <CardHeader className="pb-3">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <CardTitle className="text-xl">{find.title || find.isbn}</CardTitle>
                    <p className="text-sm text-gray-500 mt-1">ISBN: {find.isbn}</p>
                  </div>
                  <Badge className="bg-green-500 text-white text-lg px-4 py-2" data-testid="profit-badge">
                    +${find.profit.toFixed(2)}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Buy Price:</span>
                      <span className="font-semibold text-red-600" data-testid="buy-price">${find.buy_price.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Buyback Price:</span>
                      <span className="font-semibold text-green-600" data-testid="buyback-price">${find.buyback_price.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Condition:</span>
                      <span className="font-medium capitalize">{find.condition || 'N/A'}</span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Seller:</span>
                      <span className="font-medium text-right truncate max-w-[150px]" title={find.seller_name}>
                        {find.seller_name || 'N/A'}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Country:</span>
                      <span className="font-medium">{find.seller_country || 'N/A'}</span>
                    </div>
                    {/* <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Buyback Vendor:</span>
                      <span className="font-medium text-right truncate max-w-[150px]" title={find.buyback_vendor}>
                        {find.buyback_vendor || 'N/A'}
                      </span>
                    </div> */}
                  </div>
                </div>
                <div className="mt-4 flex items-center justify-between">
                  <span className="text-xs text-gray-500">
                    Found: {new Date(find.found_at).toLocaleString()}
                  </span>
                  {find.buy_link && (
                    <Button variant="outline" size="sm" asChild data-testid="view-listing-button">
                      <a href={find.buy_link} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="w-4 h-4 mr-2" />
                        View Listing
                      </a>
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-gray-50/80 px-4 py-3">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={safePage <= 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                data-testid="profitable-finds-prev-page"
              >
                <ChevronLeft className="w-4 h-4 mr-1" />
                Previous
              </Button>
              <span className="text-sm text-gray-600">
                {(safePage - 1) * pageSize + 1}–{Math.min(safePage * pageSize, finds.length)} of {finds.length}
              </span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={safePage >= totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                data-testid="profitable-finds-next-page"
              >
                Next
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
