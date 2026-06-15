/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
        // ====================================================================
        // Breakpoints — aligned dengan UI/UX Architecture Document v1.0
        // xs 0 → sm 640 → md 768 → lg 1024 → xl 1280 → 2xl 1536
        // ====================================================================
        screens: {
            sm: '640px',
            md: '768px',
            lg: '1024px',
            xl: '1280px',
            '2xl': '1536px',
        },
        extend: {
                // ============================================================
                // Typography Scale (base 16px, ratio 1.250 Major Third)
                // Token: [font-size, { lineHeight, letterSpacing, fontWeight }]
                // ============================================================
                fontSize: {
                    'display': ['3rem', { lineHeight: '3.5rem', letterSpacing: '-0.02em', fontWeight: '800' }],
                    'h1': ['2.25rem', { lineHeight: '2.75rem', letterSpacing: '-0.015em', fontWeight: '700' }],
                    'h2': ['1.75rem', { lineHeight: '2.25rem', letterSpacing: '-0.01em', fontWeight: '700' }],
                    'h3': ['1.375rem', { lineHeight: '1.875rem', letterSpacing: '0', fontWeight: '600' }],
                    'h4': ['1.125rem', { lineHeight: '1.625rem', letterSpacing: '0', fontWeight: '600' }],
                    'body-l': ['1rem', { lineHeight: '1.5rem', letterSpacing: '0', fontWeight: '400' }],
                    'body-m': ['0.875rem', { lineHeight: '1.25rem', letterSpacing: '0', fontWeight: '400' }],
                    'body-s': ['0.8125rem', { lineHeight: '1.125rem', letterSpacing: '0', fontWeight: '400' }],
                    'caption': ['0.75rem', { lineHeight: '1rem', letterSpacing: '0.01em', fontWeight: '500' }],
                    'micro': ['0.6875rem', { lineHeight: '0.875rem', letterSpacing: '0.03em', fontWeight: '600' }],
                },
                // ============================================================
                // Spacing — extends default Tailwind 4px base with semantic tokens
                // ============================================================
                spacing: {
                    '18': '4.5rem',   // 72px  — sticky form footer mobile
                    '22': '5.5rem',   // 88px  — bottom nav safe area
                    '88': '22rem',    // 352px — mobile drawer width
                    'safe-bottom': 'env(safe-area-inset-bottom)',
                    'safe-top': 'env(safe-area-inset-top)',
                },
                // ============================================================
                // Border Radius — extends shadcn defaults
                // ============================================================
                borderRadius: {
                        lg: 'var(--radius)',
                        md: 'calc(var(--radius) - 2px)',
                        sm: 'calc(var(--radius) - 4px)',
                        'xl': '0.75rem',
                        '2xl': '1rem',
                        '3xl': '1.5rem',
                },
                // ============================================================
                // Elevation (Box Shadow) — 5-tier system
                // ============================================================
                boxShadow: {
                    'elev-1': '0 1px 2px 0 rgba(15, 23, 42, 0.06)',
                    'elev-2': '0 2px 4px -1px rgba(15, 23, 42, 0.08), 0 4px 8px -2px rgba(15, 23, 42, 0.04)',
                    'elev-3': '0 4px 8px -2px rgba(15, 23, 42, 0.10), 0 8px 16px -4px rgba(15, 23, 42, 0.06)',
                    'elev-4': '0 8px 16px -4px rgba(15, 23, 42, 0.12), 0 16px 32px -8px rgba(15, 23, 42, 0.08)',
                    'elev-5': '0 16px 32px -8px rgba(15, 23, 42, 0.14), 0 32px 64px -16px rgba(15, 23, 42, 0.10)',
                    'focus-ring': '0 0 0 4px rgba(59, 130, 246, 0.15)',
                    'focus-ring-error': '0 0 0 4px rgba(239, 68, 68, 0.15)',
                    'focus-ring-success': '0 0 0 4px rgba(16, 185, 129, 0.15)',
                },
                // ============================================================
                // Timing functions & durations
                // ============================================================
                transitionTimingFunction: {
                    'spring': 'cubic-bezier(0.32, 0.72, 0, 1)',
                    'spring-back': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
                    'snap': 'cubic-bezier(0.4, 0, 0.2, 1)',
                },
                transitionDuration: {
                    '80': '80ms',
                    '180': '180ms',
                    '280': '280ms',
                    '320': '320ms',
                },
                // ============================================================
                // Colors — existing shadcn tokens + semantic additions
                // Shadcn tokens preserved to avoid breaking existing components
                // ============================================================
                colors: {
                        background: 'hsl(var(--background))',
                        foreground: 'hsl(var(--foreground))',
                        card: {
                                DEFAULT: 'hsl(var(--card))',
                                foreground: 'hsl(var(--card-foreground))'
                        },
                        popover: {
                                DEFAULT: 'hsl(var(--popover))',
                                foreground: 'hsl(var(--popover-foreground))'
                        },
                        primary: {
                                DEFAULT: 'hsl(var(--primary))',
                                foreground: 'hsl(var(--primary-foreground))'
                        },
                        secondary: {
                                DEFAULT: 'hsl(var(--secondary))',
                                foreground: 'hsl(var(--secondary-foreground))'
                        },
                        muted: {
                                DEFAULT: 'hsl(var(--muted))',
                                foreground: 'hsl(var(--muted-foreground))'
                        },
                        accent: {
                                DEFAULT: 'hsl(var(--accent))',
                                foreground: 'hsl(var(--accent-foreground))'
                        },
                        destructive: {
                                DEFAULT: 'hsl(var(--destructive))',
                                foreground: 'hsl(var(--destructive-foreground))'
                        },
                        border: 'hsl(var(--border))',
                        input: 'hsl(var(--input))',
                        ring: 'hsl(var(--ring))',
                        chart: {
                                '1': 'hsl(var(--chart-1))',
                                '2': 'hsl(var(--chart-2))',
                                '3': 'hsl(var(--chart-3))',
                                '4': 'hsl(var(--chart-4))',
                                '5': 'hsl(var(--chart-5))'
                        },
                        // Domain-specific status colors (SE 17/2024)
                        status: {
                            'found': {
                                bg: '#d1fae5',
                                border: '#10b981',
                                text: '#047857',
                            },
                            'not-found': {
                                bg: '#fee2e2',
                                border: '#ef4444',
                                text: '#b91c1c',
                            },
                            'surplus': {
                                bg: '#dbeafe',
                                border: '#3b82f6',
                                text: '#1d4ed8',
                            },
                            'dispute': {
                                bg: '#fef3c7',
                                border: '#f59e0b',
                                text: '#92400e',
                            },
                            'pending': {
                                bg: '#f1f5f9',
                                border: '#94a3b8',
                                text: '#475569',
                            },
                        },
                },
                keyframes: {
                        'accordion-down': {
                                from: { height: '0' },
                                to: { height: 'var(--radix-accordion-content-height)' }
                        },
                        'accordion-up': {
                                from: { height: 'var(--radix-accordion-content-height)' },
                                to: { height: '0' }
                        },
                        // S1 — new micro-interaction keyframes
                        'shake': {
                            '0%, 100%': { transform: 'translateX(0)' },
                            '20%, 60%': { transform: 'translateX(-4px)' },
                            '40%, 80%': { transform: 'translateX(4px)' },
                        },
                        'pulse-ring': {
                            '0%': { boxShadow: '0 0 0 0 rgba(59, 130, 246, 0.5)' },
                            '70%': { boxShadow: '0 0 0 8px rgba(59, 130, 246, 0)' },
                            '100%': { boxShadow: '0 0 0 0 rgba(59, 130, 246, 0)' },
                        },
                        'bump': {
                            '0%, 100%': { transform: 'scale(1)' },
                            '50%': { transform: 'scale(1.15)' },
                        },
                        'shimmer': {
                            '0%': { backgroundPosition: '-200% 0' },
                            '100%': { backgroundPosition: '200% 0' },
                        },
                        'fade-in': {
                            from: { opacity: '0' },
                            to: { opacity: '1' },
                        },
                        'slide-up': {
                            from: { transform: 'translateY(8px)', opacity: '0' },
                            to: { transform: 'translateY(0)', opacity: '1' },
                        },
                },
                animation: {
                        'accordion-down': 'accordion-down 0.2s ease-out',
                        'accordion-up': 'accordion-up 0.2s ease-out',
                        'shake': 'shake 400ms cubic-bezier(0.36, 0.07, 0.19, 0.97)',
                        'pulse-ring': 'pulse-ring 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                        'bump': 'bump 300ms cubic-bezier(0.34, 1.56, 0.64, 1)',
                        'shimmer': 'shimmer 1.6s linear infinite',
                        'fade-in': 'fade-in 200ms ease-out',
                        'slide-up': 'slide-up 250ms cubic-bezier(0.4, 0, 0.2, 1)',
                }
        }
  },
  plugins: [require("tailwindcss-animate")],
};
