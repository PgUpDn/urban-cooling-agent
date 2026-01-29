import React, { useState, useRef, useEffect } from 'react';
import { Message } from '../types';
import { IMG_AGENT_AVATAR, IMG_USER_AVATAR } from '../constants';
import { sendMessageToGemini } from '../services/geminiService';

interface ChatInterfaceProps {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  onConfirmSimulation: () => void;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ messages, setMessages, onConfirmSimulation }) => {
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: input,
      timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}),
      type: 'text'
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    // Call Gemini Service
    const history = messages.filter(m => m.text).map(m => ({
        role: m.sender === 'user' ? 'user' : 'model',
        parts: [{ text: m.text! }]
    }));
    
    // Add current message
    history.push({ role: 'user', parts: [{ text: userMsg.text! }] });

    const responseText = await sendMessageToGemini(input, history);
    
    setIsTyping(false);
    setMessages(prev => [...prev, {
      id: (Date.now() + 1).toString(),
      sender: 'agent',
      text: responseText,
      timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}),
      type: 'text'
    }]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <section className="flex-1 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col overflow-hidden relative mx-4 mb-4">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-slate-50/50 dark:bg-slate-900/50 backdrop-blur-sm">
        <span className="text-sm font-medium text-slate-600 dark:text-slate-300">Session ID: #CFD-2023-05-12-A</span>
        <div className="flex gap-2">
          <button className="text-slate-400 hover:text-slate-600">
            <span className="material-icons-outlined text-lg">download</span>
          </button>
          <button className="text-slate-400 hover:text-slate-600">
            <span className="material-icons-outlined text-lg">history</span>
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((msg) => (
          <div key={msg.id}>
            {msg.type === 'status' && (
              <div className="flex justify-center my-4">
                <div className="px-3 py-1 bg-slate-100 dark:bg-slate-800 rounded-full border border-slate-200 dark:border-slate-700 text-xs text-slate-500 flex items-center gap-1.5">
                  <span className="material-icons-outlined text-[14px]">cloud_sync</span>
                  {msg.text}
                </div>
              </div>
            )}

            {msg.type === 'text' && (
              <div className={`flex gap-4 ${msg.sender === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden shrink-0 border border-slate-300">
                  <img src={msg.sender === 'agent' ? IMG_AGENT_AVATAR : IMG_USER_AVATAR} alt={msg.sender} className="w-full h-full object-cover" />
                </div>
                <div className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'} max-w-[80%]`}>
                  <div className={`p-4 rounded-2xl shadow-sm text-sm leading-relaxed 
                    ${msg.sender === 'user' 
                      ? 'bg-primary text-white rounded-tr-sm' 
                      : 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 rounded-tl-sm'}`}>
                    {msg.text}
                  </div>
                  <span className="text-[10px] text-slate-400 mt-1 mx-1">{msg.timestamp}</span>
                </div>
              </div>
            )}

            {msg.type === 'form' && msg.formData && (
              <div className="flex gap-4">
                 <div className="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden shrink-0 border border-slate-300">
                  <img src={IMG_AGENT_AVATAR} alt="Agent" className="w-full h-full object-cover" />
                </div>
                <div className="flex flex-col items-start max-w-[80%]">
                    <div className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-4 shadow-sm mt-1">
                        <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Configuration Required</h4>
                        <div className="space-y-3">
                        {msg.formData.options.map((opt, idx) => (
                            <label key={opt.id} className={`flex items-center p-3 border rounded-lg cursor-pointer transition-colors ${idx === 0 ? 'border-primary bg-blue-50 dark:bg-blue-900/20' : 'border-slate-200 hover:bg-slate-50'}`}>
                            <input type="radio" name="resolution" defaultChecked={idx === 0} className="h-4 w-4 text-primary border-slate-300 focus:ring-primary" />
                            <div className="ml-3 flex-1">
                                <div className="flex justify-between">
                                <span className="block text-sm font-medium text-slate-900 dark:text-white">{opt.label}</span>
                                <span className={`text-xs font-mono font-bold ${idx === 0 ? 'text-primary' : 'text-slate-500'}`}>{opt.time}</span>
                                </div>
                                <span className="block text-xs text-slate-500">{opt.desc}</span>
                            </div>
                            </label>
                        ))}
                        <div className="pt-2 flex justify-end">
                            <button 
                                onClick={onConfirmSimulation}
                                className="bg-primary hover:bg-primary-hover text-white px-4 py-2 rounded-lg text-sm font-medium shadow-sm flex items-center gap-2 transition-colors">
                            Confirm Selection
                            <span className="material-icons-outlined text-base">arrow_forward</span>
                            </button>
                        </div>
                        </div>
                    </div>
                     <span className="text-[10px] text-slate-400 mt-1 mx-1">Agent • Just now</span>
                </div>
              </div>
            )}
          </div>
        ))}
        {isTyping && (
             <div className="flex gap-4">
                <div className="w-8 h-8 rounded-full bg-slate-200 border border-slate-300 flex items-center justify-center">
                    <span className="material-icons-outlined text-sm">smart_toy</span>
                </div>
                 <div className="bg-white border border-slate-200 p-3 rounded-2xl rounded-tl-sm shadow-sm">
                    <div className="flex gap-1">
                        <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></span>
                        <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-75"></span>
                        <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-150"></span>
                    </div>
                 </div>
             </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white dark:bg-slate-800 border-t border-slate-200 dark:border-slate-800">
        <div className="relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type instructions or override parameters..."
            className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg pl-4 pr-12 py-3 text-sm focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all shadow-sm"
          />
          <button 
            onClick={handleSend}
            className="absolute right-2 top-2 p-1.5 bg-primary text-white rounded-md hover:bg-primary-hover transition-colors shadow-sm">
            <span className="material-icons-outlined text-lg">send</span>
          </button>
        </div>
      </div>
    </section>
  );
};