import "./globals.css";

export const metadata = {
  title: "DeepShield AI | Advanced Media Authenticity Verification",
  description: "Next-generation forensic platform for deepfake detection using Neural-Inference and XAI.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
