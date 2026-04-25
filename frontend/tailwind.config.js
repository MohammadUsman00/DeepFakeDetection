/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#030712",
        foreground: "#f8fafc",
        card: {
          DEFAULT: "#111827",
          foreground: "#f8fafc",
        },
        primary: {
          DEFAULT: "#10b981", // Emerald 500
          foreground: "#ffffff",
        },
        secondary: {
          DEFAULT: "#6366f1", // Indigo 500
          foreground: "#ffffff",
        },
        muted: {
          DEFAULT: "#1e293b",
          foreground: "#94a3b8",
        },
        accent: {
          DEFAULT: "#f59e0b", // Amber 500
          foreground: "#000000",
        },
        destructive: {
          DEFAULT: "#ef4444", // Red 500
          foreground: "#ffffff",
        },
        border: "#1e293b",
        ring: "#10b981",
      },
      borderRadius: {
        lg: "0.75rem",
        md: "0.5rem",
        sm: "0.25rem",
      },
      spacing: {
        1: "4px",
        2: "8px",
        3: "12px",
        4: "16px",
        5: "20px",
        6: "24px",
        8: "32px",
        12: "48px",
        16: "64px",
      },
    },
  },
  plugins: [],
};
