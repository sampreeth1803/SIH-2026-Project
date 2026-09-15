import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ChevronDown, Download, FileJson, FileText } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export function DotMorphButton({ label, children, onClick, className = "", disabled = false, type = "button" }) {
  const reduced = useReducedMotion();
  const [hovered, setHovered] = useState(false);

  return (
    <button
      className={`dot-morph-button ${className}`}
      disabled={disabled}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      type={type}
    >
      <motion.span
        className="dot-morph-mark"
        animate={reduced || !hovered ? { width: 14, height: 14 } : { width: 10, height: 26 }}
        transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 600, damping: 24 }}
      />
      <span>{children || label}</span>
    </button>
  );
}

export function DropdownMenu({ label = "Export", items = [] }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    const close = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  return (
    <div className="smooth-dropdown" ref={rootRef}>
      <button className="dropdown-trigger" onClick={() => setOpen((value) => !value)} aria-expanded={open} type="button">
        <Download size={14} />
        <span>{label}</span>
        <ChevronDown className={open ? "rotated" : ""} size={13} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div className="dropdown-content" initial={{ opacity: 0, y: -5, scale: .97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -5, scale: .97 }} transition={{ duration: .16 }} role="menu">
            {items.map((item) => (
              <button key={item.key} className="dropdown-item" onClick={() => { item.onSelect?.(); setOpen(false); }} type="button" role="menuitem">
                {item.icon}
                <span>{item.label}</span>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function AILoader({ label = "Thinking", variant = "dots", compact = false }) {
  const reduced = useReducedMotion();
  return (
    <span className={`ai-loader ai-loader-${variant} ${compact ? "ai-loader-compact" : ""}`} role="status" aria-live="polite">
      <span>{label}</span>
      {variant === "bar" ? <span className="ai-loader-bar"><i /></span> : variant === "grid" ? <span className="ai-loader-grid">{Array.from({ length: 9 }, (_, index) => <i key={index} style={reduced ? undefined : { animationDelay: `${(index % 5) * 80}ms` }} />)}</span> : <span className="ai-loader-dots">{[0, 1, 2].map((index) => <i key={index} style={reduced ? undefined : { animationDelay: `${index * 120}ms` }} />)}</span>}
    </span>
  );
}

export function ScaleDownFade({ children, className = "" }) {
  const reduced = useReducedMotion();
  return (
    <motion.span className={className} initial={reduced ? undefined : { opacity: 0, scale: 1.04, y: 8 }} animate={reduced ? undefined : { opacity: 1, scale: 1, y: 0 }} transition={{ duration: .52, ease: [0.22, 1, 0.36, 1] }}>
      {children}
    </motion.span>
  );
}

export function SharedAxisX({ phrases, interval = 2800, className = "" }) {
  const [index, setIndex] = useState(0);
  const reduced = useReducedMotion();
  useEffect(() => {
    if (reduced || phrases.length < 2) return undefined;
    const timer = window.setInterval(() => setIndex((current) => (current + 1) % phrases.length), interval);
    return () => window.clearInterval(timer);
  }, [interval, phrases.length, reduced]);
  return (
    <span className={`shared-axis-x ${className}`} aria-live="polite">
      <AnimatePresence mode="wait">
        <motion.span key={index} initial={reduced ? undefined : { opacity: 0, x: 18, scale: .98 }} animate={{ opacity: 1, x: 0, scale: 1 }} exit={reduced ? undefined : { opacity: 0, x: -18, scale: .98 }} transition={{ duration: .38 }}>
          {phrases[index]}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

export function ShortSlideDown({ phrases, interval = 3200, className = "" }) {
  const [index, setIndex] = useState(0);
  const reduced = useReducedMotion();
  useEffect(() => {
    if (reduced || phrases.length < 2) return undefined;
    const timer = window.setInterval(() => setIndex((current) => (current + 1) % phrases.length), interval);
    return () => window.clearInterval(timer);
  }, [interval, phrases.length, reduced]);
  return (
    <span className={`short-slide-down ${className}`} aria-live="polite">
      <AnimatePresence mode="wait">
        <motion.span key={index} initial={reduced ? undefined : { opacity: 0, y: -18 }} animate={{ opacity: 1, y: 0 }} exit={reduced ? undefined : { opacity: 0, y: 10 }} transition={{ duration: .42 }}>
          {phrases[index]}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

export function AnimatedToggle({ checked, onChange, label, className = "" }) {
  const reduced = useReducedMotion();
  return (
    <button className={`animated-toggle ${checked ? "checked" : ""} ${className}`} type="button" role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange?.(!checked)}>
      <motion.span className="animated-toggle-thumb" animate={{ x: checked ? 15 : 0 }} transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 600, damping: 28 }} />
    </button>
  );
}

export const exportMenuItems = (exportReport) => [
  { key: "csv", label: "Export CSV", icon: <FileText size={14} />, onSelect: () => exportReport("csv") },
  { key: "json", label: "Export JSON", icon: <FileJson size={14} />, onSelect: () => exportReport("json") },
];
