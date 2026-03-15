import React from 'react';
import { Bot, User } from 'lucide-react';

const MessageBubble = ({ message, isBot }) => {
    return (
        <div className={`flex w-full ${isBot ? 'justify-start' : 'justify-end'} mb-4`}>
            <div className={`flex max-w-[80%] ${isBot ? 'flex-row' : 'flex-row-reverse'} items-end gap-2`}>

                {/* Avatar */}
                <div className={`flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center 
          ${isBot ? 'bg-indigo-600/50 border border-indigo-400/30' : 'bg-emerald-600/50 border border-emerald-400/30'}
        `}>
                    {isBot ? <Bot size={16} className="text-indigo-200" /> : <User size={16} className="text-emerald-200" />}
                </div>

                {/* Bubble */}
                <div className={`px-4 py-3 rounded-2xl glass-panel text-sm leading-relaxed whitespace-pre-wrap
          ${isBot ? 'rounded-bl-sm text-gray-200' : 'rounded-br-sm text-emerald-50 bg-emerald-900/20 border-emerald-500/20'}
        `}>
                    {message}
                </div>
            </div>
        </div>
    );
};

export default MessageBubble;
