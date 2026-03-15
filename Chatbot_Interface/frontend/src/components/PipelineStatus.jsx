import React from 'react';
import { Loader2, CheckCircle, Circle, AlertCircle } from 'lucide-react';

const PipelineStatus = ({ currentStep, statusMessage, isError }) => {
    const steps = [
        { id: 1, label: "Collecting Dataset" },
        { id: 2, label: "Developing Code" },
        { id: 3, label: "Training Model" },
        { id: 4, label: "Aligning Hyperparameters" },
        { id: 5, label: "DQN Strategy Scoring" },
        { id: 6, label: "Deploying Service" }
    ];
    const hasActiveStep = currentStep > 0 && currentStep < 7;

    return (
        <div className="glass-panel p-4 rounded-xl mb-6 shadow-2xl border border-indigo-500/20 bg-indigo-950/20">
            <h3 className="text-sm font-semibold text-indigo-200 mb-4 tracking-wider uppercase">Agent Pipeline Status</h3>

            <div className="space-y-3">
                {steps.map((step) => {
                    const isCompleted = currentStep > step.id || (currentStep === 7);
                    const isActive = currentStep === step.id;

                    return (
                        <div key={step.id} className="flex items-center gap-3">
                            <div className="relative flex items-center justify-center w-6 h-6">
                                {isCompleted ? (
                                    <CheckCircle size={18} className="text-emerald-400" />
                                ) : isActive ? (
                                    <Loader2 size={18} className={`animate-spin ${isError ? 'text-red-400' : 'text-indigo-400'}`} />
                                ) : (
                                    <Circle size={18} className="text-gray-600" />
                                )}
                            </div>

                            <span className={`text-sm transition-colors duration-300 ${isCompleted ? 'text-gray-300' : isActive ? (isError ? 'text-red-300 font-medium' : 'text-indigo-200 font-medium') : 'text-gray-600'
                                }`}>
                                {step.label}
                            </span>
                        </div>
                    );
                })}
            </div>

            {(statusMessage || hasActiveStep) && currentStep < 7 && (
                <div className="mt-4 pt-4 border-t border-white/10 flex items-start gap-2">
                    {isError ? <AlertCircle size={16} className="text-red-400 mt-0.5 shrink-0" /> : <div className="w-2 h-2 rounded-full bg-indigo-500 mt-1.5 shrink-0 animate-pulse-slow"></div>}
                    <p className={`text-xs ${isError ? 'text-red-300' : 'text-indigo-300'}`}>
                        {statusMessage || "Processing..."}
                    </p>
                </div>
            )}
        </div>
    );
};

export default PipelineStatus;
