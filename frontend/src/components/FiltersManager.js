import { useState, useEffect } from 'react';
import axios from 'axios';
import { RotateCcw } from 'lucide-react';
import { API } from '@/App';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { Plus, X } from 'lucide-react';

export default function FiltersManager() {
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [entityType, setEntityType] = useState('seller');
  const [bulkEntityType, setBulkEntityType] = useState('seller');
  const [value, setValue] = useState('');
  const [bulkCsv, setBulkCsv] = useState('');
  const [csvFile, setCsvFile] = useState(null); // <-- CSV file state
  const [loadingUpload, setLoadingUpload] = useState(false); // Track upload status

  useEffect(() => {
    fetchEntities();
  }, []);

  // --- Fetch all filters
  const fetchEntities = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/banned`);
      let data = [];
      if (Array.isArray(response.data)) {
        data = response.data;
      } else if (response.data?.results && Array.isArray(response.data.results)) {
        data = response.data.results;
      } else if (response.data) {
        data = Object.values(response.data).flat();
      }
      setEntities(data);
    } catch (error) {
      console.error('Fetch entities error:', error);
      toast.error('Failed to fetch filters');
    } finally {
      setLoading(false);
    }
  };

  // --- Add single filter
  const addEntity = async (e) => {
    e.preventDefault();
    if (!value.trim()) return;

    try {
      await axios.post(`${API}/banned`, { entity_type: entityType, value: value.trim() });
      toast.success('Filter added successfully');
      setValue('');
      fetchEntities();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to add filter');
    }
  };

  // --- Delete a filter
  const deleteEntity = async (id) => {
    try {
      await axios.delete(`${API}/banned/${id}`);
      toast.success('Filter removed');
      fetchEntities();
    } catch (error) {
      toast.error('Failed to remove filter');
    }
  };

  // --- Handle CSV file selection
  const addBulkEntity = (file) => {
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target.result;
      const list = text
        .split(/\r?\n/)
        .filter(Boolean);

      setBulkCsv(list);
    };
    reader.readAsText(file);
    setCsvFile(file); // keep file reference for submission
  };

  // --- CSV bulk upload
  const bulkUploadEntities = async (e) => {
    e.preventDefault();
    if (!csvFile) return;

    if (bulkCsv.length === 0) {
      toast.error('CSV is empty');
      return;
    }

    setLoadingUpload(true); // Set loading to true when uploading starts

    try {
      const response = await axios.post(`${API}/banned/bulk`, {
        entity_type: bulkEntityType,
        values: bulkCsv,
      });

      toast.success(`Added ${response.data.added} ${bulkEntityType}s (${response.data.duplicates} duplicates skipped)`);
      setCsvFile(null); // reset file input
      setBulkCsv([]);
      fetchEntities();
    } catch (err) {
      console.error(err);
      toast.error('Failed to upload CSV');
    } finally {
      setLoadingUpload(false); // Reset loading when done
    }
  };

  const resetAllBanners = async () => {
    if (!window.confirm("Are you sure you want to delete all banners?")) return;

    try {
      await axios.delete(`${API}/banned/reset`); // You’ll need to implement this endpoint
      toast.success('All banners have been deleted');
      setEntities([]);
    } catch (error) {
      toast.error('Failed to reset banners');
    }
  };

  // --- Group entities by type
  const groupedEntities = {
    seller: Array.isArray(entities) ? entities.filter(e => e.entity_type === 'seller') : [],
    country: Array.isArray(entities) ? entities.filter(e => e.entity_type === 'country') : [],
    website: Array.isArray(entities) ? entities.filter(e => e.entity_type === 'website') : [],
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
    <div className="space-y-6" data-testid="filters-page">

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-gray-800">Filter Management</h1>
          <p className="text-gray-600 mt-2">Block sellers, countries, or websites from results</p>
        </div>

        <Button
          onClick={resetAllBanners}
          variant="outline"
          className="flex items-center space-x-2  bg-cyan-600 hover:bg-cyan-800 hover:text-red-200 text-white"
          data-testid="reset-button"
        >
          <RotateCcw className="w-4 h-4" />
          <span>Reset</span>
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* --- Single filter form */}
        <Card className="shadow-lg">
          <CardHeader>
            <CardTitle>Add New Filter</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={addEntity} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="type">Filter Type</Label>
                  <Select value={entityType} onValueChange={setEntityType}>
                    <SelectTrigger id="type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="seller">Seller</SelectItem>
                      <SelectItem value="country">Country</SelectItem>
                      <SelectItem value="website">Website</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="value">Value</Label>
                  <Input
                    id="value"
                    placeholder="Enter seller, country, or website name"
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                  />
                </div>
              </div>
              <Button type="submit" className="w-full bg-cyan-600 hover:bg-cyan-800">
                <Plus className="w-4 h-5 mr-2" /> Add Filter
              </Button>
            </form>
          </CardContent>
        </Card>
        {/* --- CSV bulk upload form */}
        <Card className="shadow-lg">
          <CardHeader>
            <CardTitle>Add New Bulk Filter</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={bulkUploadEntities} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="type">Filter Type</Label>
                  <Select value={bulkEntityType} onValueChange={setBulkEntityType}>
                    <SelectTrigger id="type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="seller">Seller</SelectItem>
                      <SelectItem value="country">Country</SelectItem>
                      <SelectItem value="website">Website</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="csvFile">Upload Bulk Filter CSV</Label>
                  <Input
                    id="csvFile"
                    type="file"
                    accept=".csv"
                    onChange={(e) => addBulkEntity(e.target.files?.[0] || null)}
                  />
                </div>
              </div>
              <Button
                type="submit"
                className={`w-full bg-cyan-600 hover:bg-cyan-800 ${loadingUpload ? 'cursor-wait opacity-75' : ''}`}
                disabled={loadingUpload} // Disable button when uploading
              >
                {loadingUpload ? (
                  <div className="flex items-center justify-center space-x-2">
                    <div className="w-4 h-4 border-2 border-t-2 border-white border-transparent rounded-full animate-spin"></div>
                    <span>Uploading...</span>
                  </div>
                ) : (
                  <div className="flex items-center justify-center space-x-2">
                    <Plus className="w-4 h-5 mr-2" /> Add Bulk Filters
                  </div>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      {/* --- Filters display */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {Object.entries(groupedEntities).map(([type, items]) => (
          <Card key={type} className="shadow-lg">
            <CardHeader>
              <CardTitle className="capitalize">{type}s ({items.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {items.length === 0 ? (
                  <p className="text-center text-gray-500 py-4 text-sm">No filters</p>
                ) : (
                  items.map((entity) => (
                    <div
                      key={entity.id}
                      className="flex items-center justify-between p-2 bg-gray-50 rounded hover:bg-gray-100 transition-colors"
                    >
                      <span className="text-sm truncate">{entity.value}</span>
                      <Button
                        onClick={() => deleteEntity(entity.id)}
                        variant="ghost"
                        size="sm"
                      >
                        <X className="w-4 h-4 text-red-500" />
                      </Button>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
