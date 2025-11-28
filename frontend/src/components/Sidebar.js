import { Link, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { 
  BookOpen, 
  Home, 
  FileText, 
  Filter, 
  TrendingUp, 
  ScrollText, 
  Settings as SettingsIcon,
  LogOut,
  Menu
} from 'lucide-react';

export default function Sidebar({ isOpen, onToggle, onLogout }) {
  const location = useLocation();

  const menuItems = [
    { path: '/', icon: Home, label: 'Overview' },
    { path: '/isbns', icon: FileText, label: 'ISBN List' },
    { path: '/filters', icon: Filter, label: 'Filters' },
    { path: '/profitable', icon: TrendingUp, label: 'Profitable Finds' },
    { path: '/logs', icon: ScrollText, label: 'Logs' },
    { path: '/settings', icon: SettingsIcon, label: 'Settings' },
  ];

  return (
    <>
      <Button
        onClick={onToggle}
        className="fixed top-4 left-4 z-50 lg:hidden"
        variant="outline"
        size="icon"
        data-testid="sidebar-toggle"
      >
        <Menu className="h-5 w-5" />
      </Button>

      <aside
        className={`fixed left-0 top-0 h-full bg-white shadow-2xl z-40 transition-transform duration-300 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        } w-64`}
        data-testid="sidebar"
      >
        <div className="flex flex-col h-full bg-[#faebd7]">
          <div className="p-6 border-b border-cyan-500">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center">
                <BookOpen className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-gray-800">Book Scout</h1>
                <p className="text-xs text-gray-500">Arbitrage Finder</p>
              </div>
            </div>
          </div>

          <nav className="flex-1 p-4 space-y-2 overflow-y-auto border">
            {menuItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white'
                      : 'text-gray-700 hover:bg-violet-300 hover:text-orange-500'
                  }`}
                  data-testid={`nav-${item.label.toLowerCase().replace(' ', '-')}`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium">{item.label}</span>
                </Link>
              );
            })}
          </nav>

          <div className="p-4 border-t border-cyan-500">
            <Button
              onClick={onLogout}
              variant="outline"
              className="w-full justify-start bg-[#deb887] hover:bg-[#c5a071]"
              data-testid="logout-button"
            >
              <LogOut className="w-5 h-5 mr-3" />
              Logout
            </Button>
          </div>
        </div>
      </aside>
    </>
  );
}
