import { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { API } from '@/App';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import { Plus, Trash2, Upload, ChevronLeft, ChevronRight, FileSpreadsheet, RotateCcw } from 'lucide-react';
import { useDropzone } from "react-dropzone";

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

export default function ISBNManager() {
  const [isbns, setIsbns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newISBN, setNewISBN] = useState('');
  const [bulkISBNs, setBulkISBNs] = useState('');
  const [showBulk, setShowBulk] = useState(false);
  const [csvFileName, setCsvFileName] = useState(null);
  const [loadingUpload, setLoadingUpload] = useState(false); // New loading state for bulk upload
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  useEffect(() => {
    fetchISBNs();
  }, []);

  const totalPages = Math.max(1, Math.ceil(isbns.length / pageSize));
  const safePage = Math.min(currentPage, totalPages);

  const paginatedIsbns = useMemo(() => {
    const start = (safePage - 1) * pageSize;
    return isbns.slice(start, start + pageSize);
  }, [isbns, safePage, pageSize]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  const fetchISBNs = async () => {
    try {
      const response = await axios.get(`${API}/isbns`);
      setIsbns(response.data);
    } catch (error) {
      toast.error('Failed to fetch ISBNs');
    } finally {
      setLoading(false);
    }
  };

  const onDrop = useCallback((acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file) return;
    setCsvFileName(file.name);

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result;
      const isbns = text
        .split(/[\n,]+/)
        .map((x) => x.trim())
        .filter(Boolean)
        .join("\n");
      setBulkISBNs(isbns);
    };
    reader.readAsText(file);
  }, []);

  const resetAllISBNs = async () => {
    if (!window.confirm("Are you sure you want to delete all ISBNs?")) return;

    try {
      await axios.delete(`${API}/isbns/reset`); // You’ll need to implement this endpoint
      toast.success('All ISBNs have been deleted');
      setIsbns([]);
    } catch (error) {
      toast.error('Failed to reset ISBNs');
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

  const addISBN = async (e) => {
    e.preventDefault();
    if (!newISBN.trim()) return;

    try {
      await axios.post(`${API}/isbns?isbn=${encodeURIComponent(newISBN)}`);
      toast.success('ISBN added successfully');
      setNewISBN('');
      fetchISBNs();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to add ISBN');
    }
  };

  const bulkUpload = async () => {
    if (!bulkISBNs.trim()) return;

    const isbnList = bulkISBNs.split('\n').map(isbn => isbn.trim()).filter(isbn => isbn);

    setLoadingUpload(true); // Start the loading state

    try {
      const response = await axios.post(`${API}/isbns/bulk`, { isbns: isbnList });
      toast.success(`Added ${response.data.added} ISBNs (${response.data.duplicates} duplicates skipped)`);
      setBulkISBNs('');
      setShowBulk(false);
      fetchISBNs();
    } catch (error) {
      toast.error('Failed to upload ISBNs');
    } finally {
      setLoadingUpload(false); // End the loading state
    }
  };

  const deleteISBN = async (isbn) => {
    try {
      await axios.delete(`${API}/isbns/${encodeURIComponent(isbn)}`);
      toast.success('ISBN deleted');
      fetchISBNs();
    } catch (error) {
      toast.error('Failed to delete ISBN');
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
    <div className="space-y-6" data-testid="isbn-manager-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-gray-800">ISBN Management</h1>
          <p className="text-gray-600 mt-2">Manage your list of ISBNs to monitor</p>
        </div>

        <Button
          onClick={resetAllISBNs}
          variant="outline"
          className="flex items-center space-x-2  bg-cyan-600 hover:bg-cyan-800 hover:text-red-200 text-white"
          data-testid="reset-button"
        >
          <RotateCcw className="w-4 h-4" />
          <span>Reset</span>
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="shadow-lg">
          <CardHeader>
            <CardTitle>Add Single ISBN</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={addISBN} className="space-y-4">
              <div>
                <Label htmlFor="isbn">ISBN Number</Label>
                <Input
                  id="isbn"
                  placeholder="Enter ISBN (e.g., 9780134685991)"
                  value={newISBN}
                  onChange={(e) => setNewISBN(e.target.value)}
                  data-testid="single-isbn-input"
                />
              </div>
              <Button type="submit" className="w-full bg-cyan-600 hover:bg-cyan-800" data-testid="add-isbn-button">
                <Plus className="w-4 h-4 mr-2" />
                Add ISBN
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card className="shadow-lg">
          <CardHeader>
            <CardTitle>Bulk Upload</CardTitle>
          </CardHeader>
          <CardContent>
            {!showBulk ? (
              <Button
                onClick={() => setShowBulk(true)}
                className="w-full bg-cyan-600 hover:bg-cyan-800"
                data-testid="show-bulk-upload-button"
              >
                <Upload className="w-4 h-4 mr-2" />
                Upload Multiple ISBNs
              </Button>
            ) : (
              <div className="space-y-4">
                <Label htmlFor="bulk">Paste ISBNs (one per line)</Label>
                <Textarea
                  id="bulk"
                  placeholder="9780134685991\n9780321573513\n9781449355739"
                  rows={8}
                  value={bulkISBNs}
                  onChange={(e) => setBulkISBNs(e.target.value)}
                  data-testid="bulk-isbn-textarea"
                />

                {/* --- CSV Drag & Drop --- */}
                <div
                  {...getRootProps()}
                  className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition ${isDragActive
                      ? "border-blue-500 bg-blue-50"
                      : "border-gray-300 hover:border-blue-400"
                    }`}
                >
                  <input {...getInputProps()} />
                  <FileSpreadsheet className="w-6 h-6 mx-auto mb-2 text-blue-500" />
                  {csvFileName ? (
                    <p className="text-sm font-medium text-gray-700">
                      ✅ {csvFileName} loaded
                    </p>
                  ) : (
                    <p className="text-sm text-gray-500">
                      Drag and drop a CSV file here, or click to select
                    </p>
                  )}
                </div>

                <div className="flex space-x-2">
                <Button
                    onClick={bulkUpload}
                    className={`flex-1 bg-cyan-600 hover:bg-cyan-800 ${loadingUpload ? 'cursor-wait opacity-75' : ''}`}
                    data-testid="bulk-upload-button"
                    disabled={loadingUpload} // Disable while uploading
                  >
                    {loadingUpload ? (
                      <div className="flex items-center justify-center space-x-2">
                        {/* Spinner animation inside button */}
                        <div className="w-4 h-4 border-2 border-t-2 border-white border-transparent rounded-full animate-spin"></div>
                        <span>Uploading...</span>
                      </div>
                    ) : (
                      <div className="flex items-center justify-center space-x-2">
                        <Upload className="w-4 h-4 mr-2" />
                        <span>Upload</span>
                      </div>
                    )}
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="shadow-lg bg-[#fff8dc]">
        <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between space-y-0">
          <CardTitle>ISBN List ({isbns.length})</CardTitle>
          {isbns.length > 0 && (
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
                  data-testid="isbn-page-size"
                >
                  {PAGE_SIZE_OPTIONS.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <span className="text-gray-500" data-testid="isbn-page-info">
                Page {safePage} of {totalPages}
              </span>
            </div>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="max-h-96 overflow-y-auto">
            {isbns.length === 0 ? (
              <p className="text-center text-gray-500 py-8">No ISBNs added yet</p>
            ) : (
              <div className="space-y-2">
                {paginatedIsbns.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between p-3 bg-[#f8e5ce] rounded-lg hover:bg-[#e6cfb4] transition-colors"
                    data-testid="isbn-item"
                  >
                    <div className="flex-1">
                      <p className="font-mono font-medium">{item.isbn}</p>
                      <p className="text-xs text-gray-500">
                        Added: {new Date(item.added_at).toLocaleDateString()}
                        {item.last_checked && (
                          <span className="ml-3">
                            Last checked: {new Date(item.last_checked).toLocaleDateString()}
                          </span>
                        )}
                      </p>
                    </div>
                    <Button
                      onClick={() => deleteISBN(item.isbn)}
                      variant="destructive"
                      size="sm"
                      data-testid="delete-isbn-button"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
          {isbns.length > 0 && totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-amber-200/80 pt-4">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={safePage <= 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                data-testid="isbn-prev-page"
              >
                <ChevronLeft className="w-4 h-4 mr-1" />
                Previous
              </Button>
              <span className="text-sm text-gray-600">
                {(safePage - 1) * pageSize + 1}–{Math.min(safePage * pageSize, isbns.length)} of {isbns.length}
              </span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={safePage >= totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                data-testid="isbn-next-page"
              >
                Next
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
