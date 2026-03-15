import React from 'react';
import { ExternalLink, Rocket } from 'lucide-react';

const DeployBanner = ({ deployUrl }) => {
    if (!deployUrl) return null;

    return (
        <div className="mt-6 p-1 rounded-2xl bg-gradient-to-r from-emerald-400 via-teal-500 to-emerald-400 animate-pulse-slow shadow-2xl shadow-emerald-900/50">
            <div className="bg-emerald-950/90 rounded-xl p-5 backdrop-blur-sm h-full w-full flex flex-col sm:flex-row items-center justify-between gap-4">

                <div className="flex items-center gap-4">
                    <div className="bg-emerald-500/20 p-3 rounded-full border border-emerald-400/30">
                        <Rocket size={24} className="text-emerald-400" />
                    </div>
                    <div>
                        <h3 className="text-emerald-50 font-semibold text-lg">Deployment Successful!</h3>
                        <p className="text-emerald-200/80 text-sm">Your model and UI are now live.</p>
                    </div>
                </div>

                <a
                    href={deployUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-400 text-emerald-950 font-bold py-2.5 px-6 rounded-lg transition-colors whitespace-nowrap"
                >
                    Open App <ExternalLink size={18} />
                </a>

            </div>
        </div>
    );
};

export default DeployBanner;
