import { ReactNode } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { LogOut, Home, Package, GitForkIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface LayoutProps {
    children: ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    if (!user) return null;

    const getInitials = (name: string) => {
        return name
            .split(' ')
            .map((n) => n[0])
            .join('')
            .toUpperCase()
            .slice(0, 2);
    };

    const navigationItems = [
        {
            name: 'Home',
            href: '/',
            icon: Home,
        },
        {
            name: 'Items',
            href: '/items',
            icon: Package,
        },
        {
            name: 'Taxonomies',
            href: '/taxonomies',
            icon: GitForkIcon,
        },
    ];

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
            <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between items-center h-16">
                        <div className="flex items-center space-x-8">
                            <h1 className="text-xl font-semibold text-gray-900 dark:text-white whitespace-nowrap">
                                Topic Modeling Agent
                            </h1>

                            <nav className="hidden md:flex items-center space-x-1">
                                {navigationItems.map((item) => {
                                    const Icon = item.icon;
                                    const isActive = location.pathname === item.href;
                                    return (
                                        <Button
                                            key={item.href}
                                            variant="ghost"
                                            className={cn(
                                                "flex items-center px-3 py-2",
                                                isActive && "bg-gray-100 dark:bg-gray-700"
                                            )}
                                            onClick={() => navigate(item.href)}
                                        >
                                            <Icon className="h-4 w-4" />
                                            <span className="ml-1">{item.name}</span>
                                        </Button>
                                    );
                                })}
                            </nav>
                        </div>

                        <div className="flex items-center space-x-4">
                            {/* Mobile navigation */}
                            <DropdownMenu>
                                <DropdownMenuTrigger asChild className="md:hidden">
                                    <Button variant="ghost" size="icon">
                                        <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                                        </svg>
                                    </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end" className="w-48">
                                    {navigationItems.map((item) => {
                                        const Icon = item.icon;
                                        const isActive = location.pathname === item.href;
                                        return (
                                            <DropdownMenuItem
                                                key={item.href}
                                                onClick={() => navigate(item.href)}
                                                className={cn(
                                                    "flex items-center space-x-2",
                                                    isActive && "bg-gray-100 dark:bg-gray-700"
                                                )}
                                            >
                                                <Icon className="h-4 w-4" />
                                                <span>{item.name}</span>
                                            </DropdownMenuItem>
                                        );
                                    })}
                                </DropdownMenuContent>
                            </DropdownMenu>

                            {/* User menu */}
                            <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                    <Button variant="ghost" className="relative h-10 w-10 rounded-full">
                                        <Avatar className="h-10 w-10">
                                            <AvatarImage src={user.picture} alt={user.name} />
                                            <AvatarFallback>{getInitials(user.name)}</AvatarFallback>
                                        </Avatar>
                                    </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent className="w-56" align="end" forceMount>
                                    <DropdownMenuItem className="flex flex-col items-start">
                                        <div className="text-sm font-medium">{user.name}</div>
                                        <div className="text-xs text-gray-500">{user.email}</div>
                                    </DropdownMenuItem>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem onClick={logout} className="text-red-600 dark:text-red-400">
                                        <LogOut className="mr-2 h-4 w-4" />
                                        <span>Log out</span>
                                    </DropdownMenuItem>
                                </DropdownMenuContent>
                            </DropdownMenu>
                        </div>
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {children}
            </main>
        </div>
    );
};

export default Layout; 