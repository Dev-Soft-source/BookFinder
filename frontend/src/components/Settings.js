import { useState } from 'react';
import axios from 'axios';
import { API } from '@/App';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { Key, Mail } from 'lucide-react';

export default function Settings() {
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const changePassword = async (e) => {
    e.preventDefault();
    
    if (newPassword !== confirmPassword) {
      toast.error('New passwords do not match');
      return;
    }

    if (newPassword.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }

    setLoading(true);
    try {
      await axios.post(`${API}/auth/change-password`, {
        old_password: oldPassword,
        new_password: newPassword,
      });
      toast.success('Password changed successfully');
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to change password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="settings-page">
      <div>
        <h1 className="text-4xl font-bold text-gray-800">Settings</h1>
        <p className="text-gray-600 mt-2">Manage your account and application settings</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="shadow-lg">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Key className="w-5 h-5" />
              <span>Change Password</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={changePassword} className="space-y-4">
              <div>
                <Label htmlFor="old-password">Current Password</Label>
                <Input
                  id="old-password"
                  type="password"
                  value={oldPassword}
                  onChange={(e) => setOldPassword(e.target.value)}
                  required
                  data-testid="old-password-input"
                />
              </div>
              <div>
                <Label htmlFor="new-password">New Password</Label>
                <Input
                  id="new-password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  data-testid="new-password-input"
                />
              </div>
              <div>
                <Label htmlFor="confirm-password">Confirm New Password</Label>
                <Input
                  id="confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  data-testid="confirm-password-input"
                />
              </div>
              <Button type="submit" className="w-full bg-cyan-600 hover:bg-cyan-800" disabled={loading} data-testid="change-password-button">
                {loading ? 'Changing...' : 'Change Password'}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card className="shadow-lg">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Mail className="w-5 h-5" />
              <span>Email Notifications</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-gray-600">
              Configure email notifications for profitable finds in your environment variables.
            </p>
            <div className="bg-gray-50 p-4 rounded-lg space-y-2">
              <p className="text-sm font-mono">SMTP_SERVER = smtp.gmail.com</p>
              <p className="text-sm font-mono">SMTP_PORT = 587</p>
              <p className="text-sm font-mono">FROM_EMAIL = alerts@gmail.com</p>
              <p className="text-sm font-mono">App Password = XXXX XXXX XXXX XXXX</p>
            </div>
            <p className="text-xs text-gray-500">
              Add these to your backend .env file and restart the server.
            </p>
          </CardContent>
        </Card>
      </div>

      <Card className="shadow-lg bg-blue-50 border-blue-200">
        <CardHeader>
          <CardTitle className="text-blue-800">System Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-blue-800">
          <div className="flex justify-between py-2 border-b border-blue-200">
            <span>Check Frequency:</span>
            <span className="font-medium">Every 48 hours</span>
          </div>
          <div className="flex justify-between py-2 border-b border-blue-200">
            <span>ISBN Check Interval:</span>
            <span className="font-medium">24-48 hours per ISBN</span>
          </div>
          <div className="flex justify-between py-2 border-b border-blue-200">
            <span>Batch Size:</span>
            <span className="font-medium">20000 ISBNs per run</span>
          </div>
          <div className="flex justify-between py-2">
            <span>Scraper Engine:</span>
            <span className="font-medium">bs4 (BeautifulSoup)</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
