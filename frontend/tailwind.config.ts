import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        cream: "#FFF9F0",
        ink: "#2B2540",
        blueberry: "#5B6CFF",
        "blueberry-soft": "#EEF0FF",
        mint: "#3DD6A0",
        "mint-soft": "#E5FBF3",
        sunshine: "#FFC94D",
        "sunshine-soft": "#FFF4DA",
        coral: "#FF7E6B",
        "coral-soft": "#FFE9E5",
      },
      fontFamily: {
        display: ["var(--font-jua)", "system-ui", "sans-serif"],
        body: ["var(--font-pretendard)", "system-ui", "sans-serif"],
      },
      borderRadius: {
        blob: "1.75rem",
      },
      boxShadow: {
        soft: "0 8px 24px -8px rgba(91, 108, 255, 0.25)",
        pop: "0 12px 32px -10px rgba(43, 37, 64, 0.18)",
      },
      keyframes: {
        "bounce-soft": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-8px)" },
        },
        "pop-in": {
          "0%": { transform: "scale(0.9)", opacity: "0" },
          "100%": { transform: "scale(1)", opacity: "1" },
        },
        "fill-bar": {
          "0%": { width: "0%" },
        },
        wiggle: {
          "0%, 100%": { transform: "rotate(-3deg)" },
          "50%": { transform: "rotate(3deg)" },
        },
      },
      animation: {
        "bounce-soft": "bounce-soft 1.6s ease-in-out infinite",
        "pop-in": "pop-in 0.4s ease-out both",
        "fill-bar": "fill-bar 0.9s ease-out both",
        wiggle: "wiggle 0.8s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
