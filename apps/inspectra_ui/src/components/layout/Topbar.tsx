import { useState, useEffect, type ReactNode } from 'react';
import { Menu, Search } from 'lucide-react';
import { P, F } from '../../design/tokens';
import { BackendStatusIndicator } from '../status/BackendStatusIndicator';
import { SearchModal } from './SearchModal';
import { ProvenanceBadge } from '../ProvenanceBadge';
import type { Provenance } from '../../types/api';

interface TopbarProps {
  section?: string;
  title?: string;
  actions?: ReactNode;
  provenance?: Provenance | null;
  provenanceSource?: string;
  sidebarVisible?: boolean;
  onToggleSidebar?: () => void;
  isMobile?: boolean;
}

export function Topbar({
  section,
  title,
  actions,
  provenance,
  provenanceSource,
  sidebarVisible = true,
  onToggleSidebar,
  isMobile = false,
}: TopbarProps) {
  const [searchOpen, setSearchOpen] = useState(false);

  // ⌘K / Ctrl+K global shortcut
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setSearchOpen(o => !o);
      }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <>
      <div style={{
        height: 44, flexShrink: 0,
        borderBottom: `1px solid ${P.border}`,
        display: 'flex', alignItems: 'center', padding: isMobile ? '0 12px' : '0 20px',
        background: P.surface, gap: isMobile ? 8 : 12,
      }}>
        {onToggleSidebar && (
          <button
            type="button"
            className="topbar-hamburger"
            aria-label={sidebarVisible ? 'Hide navigation' : 'Show navigation'}
            title={sidebarVisible ? 'Hide navigation' : 'Show navigation'}
            aria-expanded={sidebarVisible}
            onClick={onToggleSidebar}
            style={{
              width: 28,
              height: 28,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              borderRadius: 6,
              border: `1px solid ${P.border}`,
              background: P.cardHi,
              color: P.textMute,
              cursor: 'pointer',
            }}
          >
            <Menu size={14} />
          </button>
        )}

        {/* Section breadcrumb — hidden on mobile via CSS */}
        {section && (
          <span className="topbar-section-text" style={{ fontSize: 11, color: P.textFaint, fontFamily: F.mono, letterSpacing: '0.06em' }}>
            {section}
          </span>
        )}
        {section && title && !isMobile && <span style={{ color: P.border }}>·</span>}
        {title && (
          <span style={{ fontSize: 13, fontWeight: 500, color: P.textDim,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: isMobile ? 140 : undefined }}>
            {title}
          </span>
        )}
        {provenanceSource && <ProvenanceBadge provenance={provenance} source={provenanceSource} />}

        <div style={{ flex: 1 }} />

        {/* Search button — icon-only on mobile, full on desktop */}
        <button
          onClick={() => setSearchOpen(true)}
          aria-label="Open search (⌘K)"
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: isMobile ? '5px 8px' : '5px 10px',
            borderRadius: 7,
            background: P.cardHi, border: `1px solid ${P.border}`,
            color: P.textMute, fontSize: 12, cursor: 'pointer',
            transition: 'border-color 0.12s',
            minWidth: isMobile ? 32 : undefined,
            minHeight: isMobile ? 36 : undefined,
            justifyContent: 'center',
          }}
          onMouseEnter={e => (e.currentTarget.style.borderColor = P.accent + '66')}
          onMouseLeave={e => (e.currentTarget.style.borderColor = P.border)}
        >
          <Search size={12} />
          {!isMobile && (
            <>
              <span>Search apps, runs, evidence…</span>
              <span style={{ marginLeft: 8, fontFamily: F.mono, fontSize: 10, color: P.textFaint }}>⌘K</span>
            </>
          )}
        </button>

        <BackendStatusIndicator />

        {actions && <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>{actions}</div>}
      </div>

      {searchOpen && <SearchModal onClose={() => setSearchOpen(false)} />}
    </>
  );
}
