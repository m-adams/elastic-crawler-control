/**
 * Site Directory Component
 * 
 * A searchable "phonebook" of demo sites with crawlability status.
 * Can be used standalone or integrated into URL input for suggestions.
 * 
 * Features:
 * - Search by name, URL, category, or tags
 * - Filter by category and status
 * - Click to select a site for crawling
 * - Shows viability status (works, partial, blocked)
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  EuiPanel,
  EuiFlexGroup,
  EuiFlexItem,
  EuiFieldSearch,
  EuiFilterGroup,
  EuiFilterButton,
  EuiBasicTable,
  EuiBadge,
  EuiLink,
  EuiText,
  EuiSpacer,
  EuiTitle,
  EuiIcon,
  EuiToolTip,
  EuiCallOut,
  EuiButtonIcon,
  EuiPopover,
  EuiSelectable,
  EuiHorizontalRule,
  EuiEmptyPrompt,
  EuiLoadingSpinner,
} from '@elastic/eui';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

// Status badge colors and icons
const STATUS_CONFIG = {
  works: { color: 'success', icon: 'check', label: 'Works' },
  partial: { color: 'warning', icon: 'alert', label: 'Partial' },
  blocked: { color: 'danger', icon: 'cross', label: 'Blocked' },
  untested: { color: 'default', icon: 'questionInCircle', label: 'Untested' },
};

// Category display names
const CATEGORY_NAMES = {
  news: 'News',
  tech_blog: 'Tech Blog',
  documentation: 'Documentation',
  ecommerce: 'E-commerce',
  developer: 'Developer',
  reference: 'Reference',
  social: 'Social',
  government: 'Government',
  education: 'Education',
};

/**
 * Status badge component
 */
function StatusBadge({ status, note }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.untested;
  
  const badge = (
    <EuiBadge color={config.color} iconType={config.icon}>
      {config.label}
    </EuiBadge>
  );
  
  if (note) {
    return (
      <EuiToolTip content={note}>
        {badge}
      </EuiToolTip>
    );
  }
  
  return badge;
}

/**
 * Main Site Directory Component
 */
export default function SiteDirectory({ 
  onSelectSite,
  compact = false,
  showHeader = true,
}) {
  // State
  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [selectedStatuses, setSelectedStatuses] = useState([]);
  const [stats, setStats] = useState(null);
  
  // Filter popovers
  const [isCategoryPopoverOpen, setIsCategoryPopoverOpen] = useState(false);
  const [isStatusPopoverOpen, setIsStatusPopoverOpen] = useState(false);

  // Fetch directory on mount
  useEffect(() => {
    async function fetchDirectory() {
      try {
        setLoading(true);
        const response = await fetch(`${API_BASE}/sites/directory`);
        if (!response.ok) throw new Error('Failed to fetch site directory');
        const data = await response.json();
        setSites(data.sites);
        setStats(data.stats);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchDirectory();
  }, []);

  // Filter sites based on search and filters
  const filteredSites = useMemo(() => {
    return sites.filter(site => {
      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const searchable = [
          site.name,
          site.url,
          site.description,
          site.category,
          ...(site.tags || []),
        ].join(' ').toLowerCase();
        
        if (!searchable.includes(query)) {
          return false;
        }
      }
      
      // Category filter
      if (selectedCategories.length > 0) {
        if (!selectedCategories.includes(site.category)) {
          return false;
        }
      }
      
      // Status filter
      if (selectedStatuses.length > 0) {
        if (!selectedStatuses.includes(site.status)) {
          return false;
        }
      }
      
      return true;
    });
  }, [sites, searchQuery, selectedCategories, selectedStatuses]);

  // Handle site selection
  const handleSelectSite = useCallback((site) => {
    if (onSelectSite) {
      onSelectSite(site);
    }
  }, [onSelectSite]);

  // Table columns
  const columns = [
    {
      field: 'name',
      name: 'Site',
      sortable: true,
      render: (name, site) => (
        <EuiFlexGroup gutterSize="s" alignItems="center" responsive={false}>
          <EuiFlexItem grow={false}>
            <EuiLink 
              onClick={() => handleSelectSite(site)}
              style={{ fontWeight: 500 }}
            >
              {name}
            </EuiLink>
          </EuiFlexItem>
        </EuiFlexGroup>
      ),
    },
    {
      field: 'category',
      name: 'Category',
      sortable: true,
      width: '120px',
      render: (category) => (
        <EuiBadge color="hollow">
          {CATEGORY_NAMES[category] || category}
        </EuiBadge>
      ),
    },
    {
      field: 'status',
      name: 'Status',
      sortable: true,
      width: '100px',
      render: (status, site) => (
        <StatusBadge status={status} note={site.status_note} />
      ),
    },
    {
      field: 'description',
      name: 'Description',
      truncateText: true,
      render: (description) => (
        <EuiText size="s" color="subdued">
          {description}
        </EuiText>
      ),
    },
    {
      name: 'Actions',
      width: '80px',
      actions: [
        {
          name: 'Use',
          description: 'Use this site',
          icon: 'arrowRight',
          type: 'icon',
          onClick: handleSelectSite,
          available: (site) => site.status !== 'blocked',
        },
        {
          name: 'Open',
          description: 'Open in new tab',
          icon: 'popout',
          type: 'icon',
          onClick: (site) => window.open(site.url, '_blank'),
        },
      ],
    },
  ];

  // Compact columns (fewer fields)
  const compactColumns = [
    columns[0], // name
    columns[2], // status
    {
      name: '',
      width: '40px',
      render: (site) => (
        <EuiButtonIcon
          iconType="arrowRight"
          aria-label="Use this site"
          onClick={() => handleSelectSite(site)}
          disabled={site.status === 'blocked'}
        />
      ),
    },
  ];

  // Category filter options
  const categoryOptions = Object.entries(CATEGORY_NAMES).map(([value, label]) => ({
    label,
    key: value,
    checked: selectedCategories.includes(value) ? 'on' : undefined,
  }));

  // Status filter options
  const statusOptions = Object.entries(STATUS_CONFIG).map(([value, config]) => ({
    label: config.label,
    key: value,
    checked: selectedStatuses.includes(value) ? 'on' : undefined,
    prepend: <EuiIcon type={config.icon} color={config.color} />,
  }));

  if (loading) {
    return (
      <EuiFlexGroup justifyContent="center" alignItems="center" style={{ minHeight: 200 }}>
        <EuiFlexItem grow={false}>
          <EuiLoadingSpinner size="xl" />
        </EuiFlexItem>
      </EuiFlexGroup>
    );
  }

  if (error) {
    return (
      <EuiCallOut title="Error loading site directory" color="danger" iconType="alert">
        {error}
      </EuiCallOut>
    );
  }

  return (
    <EuiPanel paddingSize={compact ? 's' : 'm'}>
      {showHeader && (
        <>
          <EuiFlexGroup alignItems="center" justifyContent="spaceBetween">
            <EuiFlexItem grow={false}>
              <EuiTitle size="s">
                <h3>
                  <EuiIcon type="list" /> Site Directory
                </h3>
              </EuiTitle>
            </EuiFlexItem>
            {stats && (
              <EuiFlexItem grow={false}>
                <EuiFlexGroup gutterSize="s" responsive={false}>
                  <EuiFlexItem grow={false}>
                    <EuiBadge color="success">{stats.works} working</EuiBadge>
                  </EuiFlexItem>
                  <EuiFlexItem grow={false}>
                    <EuiBadge color="warning">{stats.partial} partial</EuiBadge>
                  </EuiFlexItem>
                  <EuiFlexItem grow={false}>
                    <EuiBadge color="danger">{stats.blocked} blocked</EuiBadge>
                  </EuiFlexItem>
                </EuiFlexGroup>
              </EuiFlexItem>
            )}
          </EuiFlexGroup>
          <EuiSpacer size="m" />
        </>
      )}

      {/* Search and Filters */}
      <EuiFlexGroup gutterSize="s" responsive={false}>
        <EuiFlexItem>
          <EuiFieldSearch
            placeholder="Search sites..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            isClearable
            fullWidth
          />
        </EuiFlexItem>
        
        {!compact && (
          <EuiFlexItem grow={false}>
            <EuiFilterGroup>
              {/* Category Filter */}
              <EuiPopover
                button={
                  <EuiFilterButton
                    iconType="arrowDown"
                    onClick={() => setIsCategoryPopoverOpen(!isCategoryPopoverOpen)}
                    isSelected={isCategoryPopoverOpen}
                    numFilters={selectedCategories.length}
                    hasActiveFilters={selectedCategories.length > 0}
                    numActiveFilters={selectedCategories.length}
                  >
                    Category
                  </EuiFilterButton>
                }
                isOpen={isCategoryPopoverOpen}
                closePopover={() => setIsCategoryPopoverOpen(false)}
                panelPaddingSize="none"
              >
                <EuiSelectable
                  options={categoryOptions}
                  onChange={(newOptions) => {
                    setSelectedCategories(
                      newOptions.filter(o => o.checked === 'on').map(o => o.key)
                    );
                  }}
                >
                  {(list) => <div style={{ width: 200 }}>{list}</div>}
                </EuiSelectable>
              </EuiPopover>

              {/* Status Filter */}
              <EuiPopover
                button={
                  <EuiFilterButton
                    iconType="arrowDown"
                    onClick={() => setIsStatusPopoverOpen(!isStatusPopoverOpen)}
                    isSelected={isStatusPopoverOpen}
                    numFilters={selectedStatuses.length}
                    hasActiveFilters={selectedStatuses.length > 0}
                    numActiveFilters={selectedStatuses.length}
                  >
                    Status
                  </EuiFilterButton>
                }
                isOpen={isStatusPopoverOpen}
                closePopover={() => setIsStatusPopoverOpen(false)}
                panelPaddingSize="none"
              >
                <EuiSelectable
                  options={statusOptions}
                  onChange={(newOptions) => {
                    setSelectedStatuses(
                      newOptions.filter(o => o.checked === 'on').map(o => o.key)
                    );
                  }}
                >
                  {(list) => <div style={{ width: 180 }}>{list}</div>}
                </EuiSelectable>
              </EuiPopover>
            </EuiFilterGroup>
          </EuiFlexItem>
        )}
      </EuiFlexGroup>

      <EuiSpacer size="m" />

      {/* Scrollable Results Container */}
      <div style={{ 
        maxHeight: compact ? '300px' : '400px', 
        overflowY: 'auto',
        overflowX: 'auto',
      }}>
        {/* Results Table - wrapped to force horizontal layout */}
        <div className="site-directory-table" style={{ minWidth: compact ? 'auto' : '700px' }}>
          {filteredSites.length === 0 ? (
            <EuiEmptyPrompt
              iconType="search"
              title={<h3>No sites found</h3>}
              body={<p>Try adjusting your search or filters</p>}
            />
          ) : (
          <EuiBasicTable
            items={filteredSites}
            columns={compact ? compactColumns : columns}
            rowHeader="name"
            compressed={compact}
            tableLayout="fixed"
          />
          )}
        </div>
        
        {!compact && filteredSites.length > 0 && (
          <>
            <EuiHorizontalRule margin="m" />
            <EuiText size="xs" color="subdued">
              <p>
                <EuiIcon type="help" /> Sites marked as "Blocked" require Firecrawl for crawling.
                Click a site name to use it in the config generator.
              </p>
            </EuiText>
          </>
        )}
      </div>
    </EuiPanel>
  );
}

/**
 * Compact site suggestions for URL input autocomplete
 */
export function SiteSuggestions({ query, onSelect, maxResults = 5 }) {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!query || query.length < 2) {
      setSuggestions([]);
      return;
    }

    const fetchSuggestions = async () => {
      setLoading(true);
      try {
        const response = await fetch(
          `${API_BASE}/sites/suggest?url=${encodeURIComponent(query)}&limit=${maxResults}`
        );
        if (response.ok) {
          const data = await response.json();
          setSuggestions(data);
        }
      } catch (err) {
        console.error('Failed to fetch suggestions:', err);
      } finally {
        setLoading(false);
      }
    };

    // Debounce
    const timer = setTimeout(fetchSuggestions, 150);
    return () => clearTimeout(timer);
  }, [query, maxResults]);

  if (!query || query.length < 2 || suggestions.length === 0) {
    return null;
  }

  return (
    <EuiPanel paddingSize="s" hasShadow>
      <EuiText size="xs" color="subdued">
        <strong>Suggested sites:</strong>
      </EuiText>
      <EuiSpacer size="xs" />
      {suggestions.map((site) => (
        <EuiFlexGroup
          key={site.id}
          gutterSize="s"
          alignItems="center"
          responsive={false}
          style={{ 
            padding: '4px 8px', 
            cursor: 'pointer',
            borderRadius: 4,
          }}
          className="euiSelectableListItem"
          onClick={() => onSelect(site)}
        >
          <EuiFlexItem grow={false}>
            <StatusBadge status={site.status} />
          </EuiFlexItem>
          <EuiFlexItem>
            <EuiText size="s">
              <strong>{site.name}</strong>
              <br />
              <span style={{ color: '#69707D', fontSize: '12px' }}>{site.url}</span>
            </EuiText>
          </EuiFlexItem>
        </EuiFlexGroup>
      ))}
    </EuiPanel>
  );
}
