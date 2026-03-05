import React from 'react';
import { motion, HTMLMotionProps } from 'framer-motion';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

interface GlassPanelProps extends HTMLMotionProps<'div'> {
    children: React.ReactNode;
    variant?: 'subtle' | 'vibrant' | 'dark';
}

export const GlassPanel: React.FC<GlassPanelProps> = ({
    children,
    className,
    variant = 'dark',
    ...props
}) => {
    const getVariantStyles = () => {
        switch (variant) {
            case 'subtle':
                return 'bg-white/5 border-white/10 shadow-[0_8px_32px_0_rgba(0,0,0,0.37)]';
            case 'vibrant':
                return 'bg-fuchsia-900/10 border-fuchsia-500/20 shadow-[0_8px_32px_0_rgba(217,70,239,0.1)]';
            case 'dark':
            default:
                return 'bg-slate-900/40 border-slate-700/50 shadow-[0_8px_32px_0_rgba(15,23,42,0.8)]';
        }
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className={cn(
                'backdrop-blur-xl border rounded-2xl overflow-hidden relative',
                getVariantStyles(),
                className
            )}
            {...props}
        >
            {/* Subtle edge highlight for premium feel */}
            <div className="absolute inset-0 border border-white/5 rounded-2xl pointer-events-none" />
            {children}
        </motion.div>
    );
};
