'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Square, Bot, User, ExternalLink } from 'lucide-react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: { title: string; url: string; source: string }[];
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: 'Hi! I can search arXiv, News, and Web in parallel. What’s on your mind?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  
  // Ref to track the AbortController so we can cancel from anywhere
  const abortControllerRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new content
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg: Message = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    // Create a new controller for this specific request
    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Add a placeholder assistant message
    setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

    try {
      const response = await fetch('http://localhost:8000/api/query/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: input }),
        signal: controller.signal,
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedText = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = JSON.parse(line.replace("data: ", ""));
            
            if (data.token) {
              accumulatedText += data.token;
              setMessages(prev => {
                const updated = [...prev];
                updated[updated.length - 1].content = accumulatedText;
                return updated;
              });
            }

            if (data.sources) {
              setMessages(prev => {
                const updated = [...prev];
                updated[updated.length - 1].sources = data.sources;
                return updated;
              });
            }
          }
        }
      }
    } catch (error: any) {
      if (error.name === 'AbortError') {
        console.log("Stream stopped by user");
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: 'Connection lost. Please try again.' }]);
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  return (
    <div className="flex flex-col h-[700px] w-full max-w-4xl mx-auto bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/10 flex justify-between items-center bg-white/5">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-purple-500/20 rounded-lg">
            <Bot className="w-5 h-5 text-purple-400" />
          </div>
          <h2 className="font-bold text-white tracking-tight">TechPulse Research AI</h2>
        </div>
        {loading && (
          <button 
            onClick={handleStopGeneration}
            className="flex items-center gap-2 px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 text-xs font-medium rounded-full border border-red-500/20 transition-all"
          >
            <Square className="w-3 h-3 fill-current" />
            Stop Generating
          </button>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-6 scroll-smooth">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
              msg.role === 'user' ? 'bg-purple-600' : 'bg-slate-800 border border-white/10'
            }`}>
              {msg.role === 'user' ? <User className="w-5 h-5 text-white" /> : <Bot className="w-5 h-5 text-purple-400" />}
            </div>
            
            <div className={`flex flex-col max-w-[85%] ${msg.role === 'user' ? 'items-end' : ''}`}>
              <div className={`p-4 rounded-2xl ${
                msg.role === 'user' 
                ? 'bg-purple-600 text-white rounded-tr-none' 
                : 'bg-white/5 text-slate-100 border border-white/10 rounded-tl-none'
              }`}>
                <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                {msg.role === 'assistant' && !msg.content && loading && (
                   <span className="inline-block w-2 h-4 bg-purple-400 animate-pulse" />
                )}
              </div>

              {/* Sources UI */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 w-full">
                  {msg.sources.map((source, i) => (
                    <a 
                      key={i} 
                      href={source.url} 
                      target="_blank" 
                      className="flex items-center gap-2 p-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-xs text-purple-300 transition-colors group"
                    >
                      <ExternalLink className="w-3 h-3 flex-shrink-0" />
                      <span className="truncate">{source.title}</span>
                    </a>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Input Area */}
      <form onSubmit={handleSubmit} className="p-4 bg-white/5 border-t border-white/10">
        <div className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Search arXiv and Tech News..."
            className="w-full bg-slate-950/50 text-white placeholder-slate-500 rounded-xl px-4 py-4 pr-14 border border-white/10 focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition-all"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="absolute right-2 p-2 bg-purple-600 hover:bg-purple-500 disabled:bg-slate-800 text-white rounded-lg transition-all"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
          </button>
        </div>
        <p className="text-[10px] text-center text-slate-500 mt-2">
          Parallel RAG: Searching Google News, DuckDuckGo, and arXiv.
        </p>
      </form>
    </div>
  );
}