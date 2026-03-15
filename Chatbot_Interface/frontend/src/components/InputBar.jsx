import React, { useState } from 'react';
import { Send, Mic } from 'lucide-react';

const InputBar = ({ onSendMessage, disabled }) => {
    const [text, setText] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        if (text.trim() && !disabled) {
            onSendMessage(text);
            setText('');
        }
    };

    return (
        <form onSubmit={handleSubmit} className="flex gap-2 items-end w-full">
            <div className="relative flex-grow">
                <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            handleSubmit(e);
                        }
                    }}
                    disabled={disabled}
                    placeholder="Ask me to build an ML model or a Chatbot..."
                    className="w-full glass-input py-3 pl-4 pr-12 min-h-[50px] max-h-32 resize-none no-scrollbar shadow-inner"
                    rows={1}
                />
                <button
                    type="button"
                    className="absolute right-3 bottom-3 text-gray-400 hover:text-indigo-400 transition-colors"
                    disabled={disabled}
                >
                    <Mic size={20} />
                </button>
            </div>

            <button
                type="submit"
                disabled={disabled || !text.trim()}
                className="h-[50px] w-[50px] flex items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 hover:from-indigo-500 hover:to-violet-400 text-white shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
            >
                <Send size={20} className={text.trim() && !disabled ? "ml-1" : ""} />
            </button>
        </form>
    );
};

export default InputBar;
