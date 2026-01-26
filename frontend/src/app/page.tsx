'use client';

import { useState } from 'react';
import Chat from '@/components/Chat';

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <header className="border-b border-white/10 bg-black/20 backdrop-blur-lg">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-3xl font-bold text-white">TechPulse AI</h1>
          <p className="text-purple-300">Real-time Tech Intelligence</p>
        </div>
      </header>
      
      <main className="container mx-auto px-4 py-8">
        <Chat />
      </main>
    </div>
  );
}
