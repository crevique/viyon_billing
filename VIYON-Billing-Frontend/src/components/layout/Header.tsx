import React, { useState, useEffect } from 'react';
import { Menu, ShoppingCart, User as UserIcon, Calendar, Clock } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/useAuthStore';

interface HeaderProps {
  onToggleSidebar: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onToggleSidebar }) => {
  const { user, role } = useAuthStore();
  const location = useLocation();
  const [time, setTime] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTime(
        new Intl.DateTimeFormat('en-IN', {
          timeZone: 'Asia/Kolkata',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true,
        }).format(now)
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  const todayDate = new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata',
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(new Date());

  const isPOS = location.pathname === '/pos';

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-zinc-200 bg-white/95 px-4 backdrop-blur-md sm:px-6 lg:px-8">
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          aria-label="Toggle Navigation"
          className="rounded-lg p-2 text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>

        <div className="flex flex-col">
          <div className="flex items-center gap-1.5 sm:gap-2">
            <h1 className="font-serif text-xs sm:text-sm font-bold tracking-wider text-zinc-900 truncate">
              VIYON STORE
            </h1>
            <span className="rounded bg-amber-100 px-1 sm:px-1.5 py-0.5 text-[9px] sm:text-[10px] font-semibold text-amber-800">
              POS v1.0
            </span>
          </div>
          <p className="hidden sm:block text-[11px] text-zinc-500">
            Sathyamangalam, Tamil Nadu • 082702 42681
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-4 shrink-0">
        {/* Date and Time (IST) */}
        <div className="hidden md:flex items-center gap-3 text-xs text-zinc-500 border-r border-zinc-200 pr-4">
          <span className="flex items-center gap-1.5">
            <Calendar className="h-3.5 w-3.5 text-zinc-400" />
            {todayDate}
          </span>
          <span className="flex items-center gap-1.5 font-mono text-zinc-700 font-medium">
            <Clock className="h-3.5 w-3.5 text-zinc-400" />
            {time}
          </span>
        </div>

        {/* Quick POS Action button if not already on POS */}
        {!isPOS && (
          <Link
            to="/pos"
            className="flex items-center gap-1.5 sm:gap-2 rounded-lg bg-amber-500 px-2.5 sm:px-3 py-1.5 text-xs font-semibold text-zinc-950 shadow-sm transition-all hover:bg-amber-400 active:scale-95 shrink-0"
          >
            <ShoppingCart className="h-4 w-4" />
            <span className="hidden xs:inline sm:inline">Open POS</span>
            <span className="xs:hidden sm:hidden">POS</span>
          </Link>
        )}

        {/* User Badge */}
        <div className="flex items-center gap-2 rounded-lg border border-zinc-200 bg-zinc-50 px-2 sm:px-2.5 py-1.5 shrink-0">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-zinc-200 text-zinc-700 shrink-0">
            <UserIcon className="h-3.5 w-3.5" />
          </div>
          <div className="hidden sm:flex sm:flex-col text-left">
            <span className="text-xs font-semibold text-zinc-800 leading-tight">
              {user?.full_name || 'Staff User'}
            </span>
            <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">
              {role || 'STAFF'}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};
