/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '"Plus Jakarta Sans"',
          'Inter',
          'system-ui',
          '-apple-system',
          'sans-serif',
        ],
      },
      colors: {
        // Brand accent (matches the historical #6D5EF5 primary button)
        accent: {
          50: '#f1effe',
          100: '#e5e1fd',
          200: '#cdc6fb',
          300: '#ada2f8',
          400: '#8f7df6',
          500: '#6D5EF5',
          600: '#5b48e8',
          700: '#4c39cc',
          800: '#3d2fa5',
          900: '#332a84',
        },
        // Soft semantic colors for status states
        success: { soft: '#ecfdf5', solid: '#059669', text: '#065f46' },
        warning: { soft: '#fffbeb', solid: '#d97706', text: '#92400e' },
        error: { soft: '#fef2f2', solid: '#dc2626', text: '#991b1b' },
        info: { soft: '#eff6ff', solid: '#2563eb', text: '#1e40af' },
      },
      boxShadow: {
        card: '0 1px 2px rgba(16, 24, 40, 0.04), 0 1px 3px rgba(16, 24, 40, 0.06)',
        'card-hover':
          '0 4px 8px -2px rgba(16, 24, 40, 0.08), 0 12px 24px -6px rgba(109, 94, 245, 0.12)',
        glass: '0 8px 32px rgba(31, 38, 135, 0.08)',
      },
      borderRadius: {
        card: '14px',
      },
      keyframes: {
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        'pulse-dot': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.35' },
        },
      },
      animation: {
        shimmer: 'shimmer 1.6s infinite',
        'pulse-dot': 'pulse-dot 1.8s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
