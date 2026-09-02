/** Shared UI component library — the single source of visual truth.
 *
 * Every page composes these instead of one-off styles: Card, GlassCard,
 * Button, Badge, StatCard, EmptyState, LoadingSkeleton, ChartCard,
 * PageHeader, SectionTitle. Framer Motion variants live here too so
 * staggered mount animations are consistent app-wide.
 */

import { motion } from 'framer-motion'
import type { ReactNode } from 'react'

/* ---------------- Motion variants ---------------- */

export const fadeUp = {
  hidden: { opacity: 0, y: 14 },
  visible: { opacity: 1, y: 0 },
}

export const staggerContainer = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06 } },
}

export const listItem = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.25 } },
}

/* ---------------- Card ---------------- */

export function Card({
  children,
  className = '',
  hover = false,
  padded = true,
}: {
  children: ReactNode
  className?: string
  hover?: boolean
  padded?: boolean
}) {
  return (
    <div
      className={`rounded-card bg-white shadow-card transition-shadow duration-200 ${
        hover ? 'hover:shadow-card-hover' : ''
      } ${padded ? 'p-6' : ''} ${className}`}
    >
      {children}
    </div>
  )
}

/** Frosted-glass card — for floating panels, NOT dense tables. */
export function GlassCard({
  children,
  className = '',
  padded = true,
}: {
  children: ReactNode
  className?: string
  padded?: boolean
}) {
  return (
    <div className={`glass rounded-card ${padded ? 'p-6' : ''} ${className}`}>
      {children}
    </div>
  )
}

/* ---------------- Button ---------------- */

type ButtonVariant = 'primary' | 'secondary' | 'success' | 'danger' | 'ghost'

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary:
    'bg-accent-500 text-white hover:bg-accent-600 shadow-sm hover:shadow-md',
  secondary:
    'border border-accent-200 bg-white text-accent-700 hover:bg-accent-50',
  success:
    'bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm hover:shadow-md',
  danger: 'bg-red-50 text-red-600 hover:bg-red-100 border border-red-200',
  ghost: 'text-slate-600 hover:bg-slate-100',
}

export function Button({
  children,
  onClick,
  disabled = false,
  variant = 'primary',
  className = '',
  type = 'button',
  title,
}: {
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  variant?: ButtonVariant
  className?: string
  type?: 'button' | 'submit'
  title?: string
}) {
  return (
    <motion.button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled}
      whileHover={disabled ? undefined : { scale: 1.02 }}
      whileTap={disabled ? undefined : { scale: 0.97 }}
      transition={{ duration: 0.15 }}
      className={`inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${BUTTON_STYLES[variant]} ${className}`}
    >
      {children}
    </motion.button>
  )
}

/* ---------------- Badge ---------------- */

type BadgeTone = 'accent' | 'success' | 'warning' | 'error' | 'info' | 'neutral'

const BADGE_STYLES: Record<BadgeTone, string> = {
  accent: 'bg-accent-50 text-accent-700 border-accent-100',
  success: 'bg-success-soft text-success-text border-emerald-100',
  warning: 'bg-warning-soft text-warning-text border-amber-100',
  error: 'bg-error-soft text-error-text border-red-100',
  info: 'bg-info-soft text-info-text border-blue-100',
  neutral: 'bg-slate-50 text-slate-600 border-slate-200',
}

export function Badge({
  children,
  tone = 'neutral',
  className = '',
  title,
}: {
  children: ReactNode
  tone?: BadgeTone
  className?: string
  title?: string
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${BADGE_STYLES[tone]} ${className}`}
    >
      {children}
    </span>
  )
}

/* ---------------- StatCard ---------------- */

export function StatCard({
  icon,
  label,
  value,
  trend,
  tone = 'accent',
}: {
  icon: ReactNode
  label: string
  value: ReactNode
  trend?: { dir: 'up' | 'down' | 'flat'; pct?: string }
  tone?: 'accent' | 'success' | 'warning' | 'error' | 'info'
}) {
  const toneBg: Record<string, string> = {
    accent: 'bg-accent-50 text-accent-600',
    success: 'bg-success-soft text-success-solid',
    warning: 'bg-warning-soft text-warning-solid',
    error: 'bg-error-soft text-error-solid',
    info: 'bg-info-soft text-info-solid',
  }
  return (
    <motion.div variants={listItem} whileHover={{ y: -3 }} className="rounded-card bg-white p-5 shadow-card transition-shadow hover:shadow-card-hover">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-xs font-semibold uppercase tracking-wide text-slate-400">
            {label}
          </p>
          <p className="mt-1.5 text-3xl font-extrabold tracking-tight text-slate-900">
            {value}
          </p>
          {trend && (
            <p
              className={`mt-1 text-xs font-semibold ${
                trend.dir === 'up'
                  ? 'text-emerald-600'
                  : trend.dir === 'down'
                    ? 'text-red-500'
                    : 'text-slate-400'
              }`}
            >
              {trend.dir === 'up' ? '↑' : trend.dir === 'down' ? '↓' : '→'}{' '}
              {trend.pct ?? ''}
            </p>
          )}
        </div>
        <div className={`shrink-0 rounded-xl p-2.5 ${toneBg[tone]}`}>{icon}</div>
      </div>
    </motion.div>
  )
}

/* ---------------- Page header pattern ---------------- */

export function PageHeader({
  title,
  description,
  icon,
  actions,
}: {
  title: string
  description: string
  icon?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-start gap-3">
        {icon && (
          <div className="mt-0.5 rounded-xl bg-accent-50 p-2.5 text-accent-600">
            {icon}
          </div>
        )}
        <div>
          <h1 className="text-xl font-extrabold tracking-tight text-slate-900">
            {title}
          </h1>
          <p className="mt-0.5 max-w-2xl text-sm leading-relaxed text-slate-500">
            {description}
          </p>
        </div>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}

export function SectionTitle({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <h3
      className={`text-xs font-bold uppercase tracking-widest text-slate-400 ${className}`}
    >
      {children}
    </h3>
  )
}

/* ---------------- EmptyState ---------------- */

export function EmptyState({
  icon,
  title,
  hint,
}: {
  icon?: ReactNode
  title: string
  hint?: string
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-card border border-dashed border-slate-200 bg-slate-50/60 px-6 py-10 text-center">
      {icon && <div className="text-slate-300">{icon}</div>}
      <p className="text-sm font-semibold text-slate-600">{title}</p>
      {hint && <p className="max-w-sm text-xs text-slate-400">{hint}</p>}
    </div>
  )
}

/* ---------------- LoadingSkeleton ---------------- */

export function LoadingSkeleton({ rows = 3, className = '' }: { rows?: number; className?: string }) {
  return (
    <div className={`space-y-3 ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton h-12 w-full" />
      ))}
    </div>
  )
}

export function ChartSkeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton h-64 w-full rounded-card ${className}`} />
}

/* ---------------- ChartCard ---------------- */

export function ChartCard({
  title,
  subtitle,
  controls,
  children,
  footer,
}: {
  title: string
  subtitle?: string
  controls?: ReactNode
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <motion.div variants={listItem} className="rounded-card bg-white p-5 shadow-card transition-shadow hover:shadow-card-hover">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-bold text-slate-800">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
        </div>
        {controls}
      </div>
      {children}
      {footer && <div className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-400">{footer}</div>}
    </motion.div>
  )
}
