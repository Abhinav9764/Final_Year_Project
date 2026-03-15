import React, { useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';
import PipelineStatus from './PipelineStatus';

const ChatWindow = ({ messages, pipelineState }) => {
    const bottomRef = useRef(null);

    // Auto-scroll to bottom when new messages or pipeline state changes
    useEffect(() => {
        if (bottomRef.current) {
            bottomRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages, pipelineState]);

    return (
        <div className="flex-grow overflow-y-auto no-scrollbar p-4 space-y-6">

            {/* Intro message */}
            <div className="text-center text-gray-500 text-sm my-6 pb-6 border-b border-white/5">
                <h2 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-violet-400 mb-2">
                    RAD-ML Orchestrator
                </h2>
                <p>I can build Predictive ML models or Chatbots for you.</p>
                <p>Just tell me what you need.</p>
            </div>

            {messages.map((msg, index) => (
                <MessageBubble key={index} message={msg.text} isBot={msg.isBot} />
            ))}

            {/* Render Pipeline animation block if active */}
            {pipelineState.isActive && (
                <div className="w-full flex justify-start mb-4">
                    <div className="w-[85%] md:w-[70%] lg:w-[60%]">
                        <PipelineStatus
                            currentStep={pipelineState.step}
                            statusMessage={pipelineState.message}
                            isError={pipelineState.isError}
                        />
                    </div>
                </div>
            )}

            {/* Invisible element to scroll to */}
            <div ref={bottomRef} className="h-4" />
        </div>
    );
};

export default ChatWindow;
