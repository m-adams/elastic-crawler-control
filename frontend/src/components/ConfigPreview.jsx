/**
 * ConfigPreview Component
 * 
 * Displays generated Open Crawler YAML config with:
 * - Syntax highlighting
 * - Copy to clipboard
 * - Download as YAML file
 * - Sample document preview side-by-side
 * 
 * @see Beads issue 2u9 - Phase 3.2: Config Preview & Export
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  EuiPanel,
  EuiFlexGroup,
  EuiFlexItem,
  EuiButton,
  EuiButtonEmpty,
  EuiText,
  EuiSpacer,
  EuiCode,
  EuiCopy,
  EuiCallOut,
  EuiTabs,
  EuiTab,
  EuiIcon,
  EuiToolTip,
  EuiBadge,
  EuiTitle,
  EuiTextArea,
  EuiLoadingSpinner,
} from '@elastic/eui';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

/**
 * YAML display with basic syntax highlighting
 * Note: EuiCode doesn't have native YAML highlighting,
 * so we use a simple monospace display with line numbers
 */
function YamlDisplay({ content }) {
  if (!content) {
    return (
      <EuiText color="subdued" size="s">
        No configuration generated yet.
      </EuiText>
    );
  }
  
  const lines = content.split('\n');
  
  return (
    <div 
      style={{ 
        fontFamily: 'monospace',
        fontSize: '13px',
        lineHeight: '1.5',
        backgroundColor: '#1D1E24',
        color: '#DFE5EF',
        padding: '16px',
        borderRadius: '6px',
        overflow: 'auto',
        maxHeight: '500px',
      }}
    >
      {lines.map((line, idx) => (
        <div key={idx} style={{ display: 'flex' }}>
          {/* Line number */}
          <span 
            style={{ 
              color: '#535966',
              width: '40px',
              textAlign: 'right',
              paddingRight: '16px',
              userSelect: 'none',
              flexShrink: 0,
            }}
          >
            {idx + 1}
          </span>
          {/* Line content with basic highlighting */}
          <span style={{ flex: 1 }}>
            <YamlLine content={line} />
          </span>
        </div>
      ))}
    </div>
  );
}

/**
 * Basic YAML syntax highlighting for a single line
 */
function YamlLine({ content }) {
  // Comment
  if (content.trim().startsWith('#')) {
    return <span style={{ color: '#6B7280' }}>{content}</span>;
  }
  
  // Key-value pair
  const keyMatch = content.match(/^(\s*)([a-zA-Z_][a-zA-Z0-9_-]*)(\s*:\s*)(.*)?$/);
  if (keyMatch) {
    const [, indent, key, colon, value] = keyMatch;
    return (
      <>
        <span>{indent}</span>
        <span style={{ color: '#F472B6' }}>{key}</span>
        <span style={{ color: '#DFE5EF' }}>{colon}</span>
        {value && <YamlValue value={value} />}
      </>
    );
  }
  
  // List item
  const listMatch = content.match(/^(\s*)(-)(\s+)(.*)$/);
  if (listMatch) {
    const [, indent, dash, space, value] = listMatch;
    return (
      <>
        <span>{indent}</span>
        <span style={{ color: '#FBBF24' }}>{dash}</span>
        <span>{space}</span>
        <YamlValue value={value} />
      </>
    );
  }
  
  return <span>{content}</span>;
}

/**
 * Highlight YAML values by type
 */
function YamlValue({ value }) {
  // String in quotes
  if (value.startsWith('"') || value.startsWith("'")) {
    return <span style={{ color: '#A5D6A7' }}>{value}</span>;
  }
  
  // Number
  if (/^-?\d+(\.\d+)?$/.test(value.trim())) {
    return <span style={{ color: '#90CAF9' }}>{value}</span>;
  }
  
  // Boolean
  if (/^(true|false)$/i.test(value.trim())) {
    return <span style={{ color: '#CE93D8' }}>{value}</span>;
  }
  
  // URL
  if (value.includes('://')) {
    return <span style={{ color: '#80DEEA' }}>{value}</span>;
  }
  
  return <span style={{ color: '#A5D6A7' }}>{value}</span>;
}

/**
 * Editable YAML Editor with line numbers
 */
function YamlEditor({ content, onChange, disabled }) {
  const textareaRef = useRef(null);
  const lineNumbersRef = useRef(null);
  
  const lines = (content || '').split('\n');
  const lineCount = lines.length;
  
  // Sync scroll between textarea and line numbers
  const handleScroll = useCallback(() => {
    if (lineNumbersRef.current && textareaRef.current) {
      lineNumbersRef.current.scrollTop = textareaRef.current.scrollTop;
    }
  }, []);
  
  return (
    <div 
      style={{ 
        display: 'flex',
        fontFamily: 'monospace',
        fontSize: '13px',
        lineHeight: '1.5',
        backgroundColor: '#1D1E24',
        borderRadius: '6px',
        overflow: 'hidden',
        maxHeight: '500px',
      }}
    >
      {/* Line numbers */}
      <div
        ref={lineNumbersRef}
        style={{
          color: '#535966',
          backgroundColor: '#16171D',
          padding: '16px 8px 16px 16px',
          textAlign: 'right',
          userSelect: 'none',
          overflow: 'hidden',
          flexShrink: 0,
          minWidth: '50px',
        }}
      >
        {Array.from({ length: lineCount }, (_, i) => (
          <div key={i}>{i + 1}</div>
        ))}
      </div>
      
      {/* Editable textarea */}
      <textarea
        ref={textareaRef}
        value={content || ''}
        onChange={(e) => onChange(e.target.value)}
        onScroll={handleScroll}
        disabled={disabled}
        spellCheck={false}
        style={{
          flex: 1,
          backgroundColor: '#1D1E24',
          color: '#DFE5EF',
          border: 'none',
          outline: 'none',
          padding: '16px',
          resize: 'none',
          fontFamily: 'inherit',
          fontSize: 'inherit',
          lineHeight: 'inherit',
          overflow: 'auto',
          minHeight: '300px',
        }}
      />
    </div>
  );
}

/**
 * Validation Results Display
 */
function ValidationResults({ result, isValidating }) {
  if (isValidating) {
    return (
      <EuiCallOut color="primary" iconType="clock" title="Validating...">
        <EuiFlexGroup alignItems="center" gutterSize="s">
          <EuiFlexItem grow={false}>
            <EuiLoadingSpinner size="s" />
          </EuiFlexItem>
          <EuiFlexItem>
            <EuiText size="s">Running crawler validation...</EuiText>
          </EuiFlexItem>
        </EuiFlexGroup>
      </EuiCallOut>
    );
  }
  
  if (!result) return null;
  
  const { valid, errors = [], warnings = [], crawlerAvailable } = result;
  
  if (valid && errors.length === 0 && warnings.length === 0) {
    return (
      <EuiCallOut color="success" iconType="check" title="Config is valid">
        <EuiText size="s">
          {crawlerAvailable 
            ? 'Validated against real Open Crawler binary.'
            : 'Passed schema validation. (Crawler binary not available for full validation)'}
        </EuiText>
      </EuiCallOut>
    );
  }
  
  return (
    <div>
      {errors.length > 0 && (
        <EuiCallOut color="danger" iconType="error" title={`${errors.length} error${errors.length !== 1 ? 's' : ''}`}>
          <ul style={{ margin: 0, paddingLeft: '20px' }}>
            {errors.map((err, i) => (
              <li key={i}><EuiText size="s">{err}</EuiText></li>
            ))}
          </ul>
        </EuiCallOut>
      )}
      
      {warnings.length > 0 && (
        <>
          {errors.length > 0 && <EuiSpacer size="s" />}
          <EuiCallOut color="warning" iconType="warning" title={`${warnings.length} warning${warnings.length !== 1 ? 's' : ''}`}>
            <ul style={{ margin: 0, paddingLeft: '20px' }}>
              {warnings.map((warn, i) => (
                <li key={i}><EuiText size="s">{warn}</EuiText></li>
              ))}
            </ul>
          </EuiCallOut>
        </>
      )}
    </div>
  );
}

/**
 * Sample Document Preview
 */
function SampleDocumentPreview({ document }) {
  if (!document || Object.keys(document).length === 0) {
    return (
      <EuiCallOut color="warning" iconType="help" title="No Sample Document">
        <p>Run extraction testing to see a real sample document.</p>
      </EuiCallOut>
    );
  }
  
  return (
    <div 
      style={{ 
        fontFamily: 'monospace',
        fontSize: '13px',
        lineHeight: '1.5',
        backgroundColor: '#1D1E24',
        color: '#DFE5EF',
        padding: '16px',
        borderRadius: '6px',
        overflow: 'auto',
        maxHeight: '500px',
      }}
    >
      <pre style={{ margin: 0 }}>
        {JSON.stringify(document, null, 2)}
      </pre>
    </div>
  );
}

/**
 * Crawl Rules Display Component
 * 
 * Shows crawl rules in a user-friendly format with:
 * - Summary of crawl scope (what's allowed vs denied)
 * - Ordered table of rules with color-coded policies
 * - Example URL hints for each pattern type
 */
function CrawlRulesDisplay({ rules }) {
  if (!rules || rules.length === 0) {
    return (
      <EuiCallOut color="primary" iconType="iInCircle" title="No Crawl Rules">
        <p>No crawl rules configured. All URLs on this domain will be crawled (up to max_crawl_depth).</p>
      </EuiCallOut>
    );
  }
  
  // Analyze rules for summary
  const allowRules = rules.filter(r => r.policy === 'allow');
  const denyRules = rules.filter(r => r.policy === 'deny');
  const hasCatchAllDeny = rules.some(r => r.policy === 'deny' && r.type === 'regex' && r.pattern === '.*');
  
  // Generate summary text
  const getSummaryText = () => {
    if (allowRules.length === 0 && denyRules.length > 0) {
      return 'Blocking specific paths. All other URLs will be crawled.';
    }
    if (allowRules.length > 0 && hasCatchAllDeny) {
      const allowedPaths = allowRules.map(r => r.pattern).join(', ');
      return `Allowlist mode: Only crawling ${allowedPaths}. All other paths blocked.`;
    }
    if (allowRules.length > 0) {
      return 'Mixed rules: Some paths explicitly allowed, some denied.';
    }
    return 'Custom crawl rules configured.';
  };
  
  // Get example URLs for a pattern
  const getExampleUrls = (type, pattern) => {
    const examples = {
      begins: {
        '/blog/': ['/blog/my-post', '/blog/category/tech'],
        '/products/': ['/products/item-123', '/products/category/shoes'],
        '/docs/': ['/docs/getting-started', '/docs/api/reference'],
        '/admin/': ['/admin/dashboard', '/admin/users'],
        '/login/': ['/login', '/login/oauth'],
        '/cart/': ['/cart', '/cart/checkout'],
        '/checkout/': ['/checkout', '/checkout/payment'],
      },
      contains: {
        '?': ['/page?id=1', '/search?q=test'],
        'product': ['/products/item', '/category/product-list'],
      },
      ends: {
        '.html': ['/page.html', '/blog/post.html'],
        '.pdf': ['/docs/manual.pdf', '/files/report.pdf'],
      },
      regex: {
        '.*': ['(matches everything)'],
        '\\d{4}': ['/2024/', '/2025/'],
        '/page/\\d+': ['/page/1', '/page/42'],
      },
      equals: {
        '/': ['/ (homepage only)'],
        '/about': ['/about (exact match)'],
      },
    };
    
    // Try to find matching examples
    if (examples[type]?.[pattern]) {
      return examples[type][pattern];
    }
    
    // Generate generic examples based on type
    switch (type) {
      case 'begins':
        return [`${pattern}...`, `${pattern}subpath`];
      case 'ends':
        return [`/path${pattern}`, `/other${pattern}`];
      case 'contains':
        return [`/path-with-${pattern}`, `/${pattern}/in/middle`];
      case 'regex':
        return ['(regex pattern)'];
      case 'equals':
        return [`${pattern} (exact)`];
      default:
        return [];
    }
  };
  
  // Get human-readable type description
  const getTypeDescription = (type) => {
    const descriptions = {
      begins: 'Path starts with',
      ends: 'Path ends with',
      contains: 'Path contains',
      regex: 'Matches regex',
      equals: 'Exact match',
    };
    return descriptions[type] || type;
  };
  
  return (
    <div>
      {/* Summary Section */}
      <EuiCallOut 
        color={hasCatchAllDeny ? 'primary' : 'warning'} 
        iconType={hasCatchAllDeny ? 'check' : 'alert'}
        title="Crawl Scope"
        size="s"
      >
        <p style={{ margin: 0 }}>{getSummaryText()}</p>
        {!hasCatchAllDeny && denyRules.length > 0 && (
          <EuiText size="xs" color="subdued" style={{ marginTop: '4px' }}>
            <em>Tip: Without a catch-all deny rule, unlisted paths will be crawled.</em>
          </EuiText>
        )}
      </EuiCallOut>
      
      <EuiSpacer size="m" />
      
      {/* Quick Summary Badges */}
      <EuiFlexGroup gutterSize="s" wrap>
        {allowRules.length > 0 && (
          <EuiFlexItem grow={false}>
            <EuiBadge color="success">
              {allowRules.length} allow rule{allowRules.length !== 1 ? 's' : ''}
            </EuiBadge>
          </EuiFlexItem>
        )}
        {denyRules.length > 0 && (
          <EuiFlexItem grow={false}>
            <EuiBadge color="danger">
              {denyRules.length} deny rule{denyRules.length !== 1 ? 's' : ''}
            </EuiBadge>
          </EuiFlexItem>
        )}
        {hasCatchAllDeny && (
          <EuiFlexItem grow={false}>
            <EuiBadge color="hollow">Allowlist mode</EuiBadge>
          </EuiFlexItem>
        )}
      </EuiFlexGroup>
      
      <EuiSpacer size="m" />
      
      {/* Rules Table */}
      <EuiPanel color="subdued" paddingSize="m">
        <EuiText size="xs" color="subdued" style={{ marginBottom: '8px' }}>
          <strong>Rule Order Matters:</strong> Rules are evaluated top-to-bottom. First matching rule wins.
        </EuiText>
        
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #D3DAE6' }}>
              <th style={{ textAlign: 'center', padding: '8px 12px', width: '50px' }}>#</th>
              <th style={{ textAlign: 'center', padding: '8px 12px', width: '80px' }}>Policy</th>
              <th style={{ textAlign: 'left', padding: '8px 12px', width: '120px' }}>Type</th>
              <th style={{ textAlign: 'left', padding: '8px 12px' }}>Pattern</th>
              <th style={{ textAlign: 'left', padding: '8px 12px' }}>Example Matches</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule, idx) => {
              const examples = getExampleUrls(rule.type, rule.pattern);
              const isAllow = rule.policy === 'allow';
              const isCatchAll = rule.type === 'regex' && rule.pattern === '.*';
              
              return (
                <tr 
                  key={idx} 
                  style={{ 
                    borderBottom: '1px solid #EEF2F7',
                    backgroundColor: isCatchAll ? '#FEF3C7' : 'transparent',
                  }}
                >
                  <td style={{ textAlign: 'center', padding: '10px 12px' }}>
                    <EuiBadge color="hollow">{idx + 1}</EuiBadge>
                  </td>
                  <td style={{ textAlign: 'center', padding: '10px 12px' }}>
                    <EuiBadge 
                      color={isAllow ? 'success' : 'danger'}
                      iconType={isAllow ? 'check' : 'cross'}
                    >
                      {rule.policy}
                    </EuiBadge>
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <EuiToolTip content={getTypeDescription(rule.type)}>
                      <EuiCode>{rule.type}</EuiCode>
                    </EuiToolTip>
                  </td>
                  <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontSize: '13px' }}>
                    {isCatchAll ? (
                      <EuiToolTip content="Matches all remaining URLs">
                        <span style={{ color: '#B45309' }}>{rule.pattern}</span>
                      </EuiToolTip>
                    ) : (
                      <span>{rule.pattern}</span>
                    )}
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <EuiText size="xs" color="subdued">
                      {examples.slice(0, 2).map((ex, i) => (
                        <span key={i}>
                          {i > 0 && ', '}
                          <code style={{ fontSize: '11px' }}>{ex}</code>
                        </span>
                      ))}
                    </EuiText>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </EuiPanel>
      
      {/* Legend */}
      <EuiSpacer size="s" />
      <EuiText size="xs" color="subdued">
        <EuiFlexGroup gutterSize="m" alignItems="center">
          <EuiFlexItem grow={false}>
            <strong>Pattern types:</strong>
          </EuiFlexItem>
          <EuiFlexItem grow={false}>
            <code>begins</code> = starts with
          </EuiFlexItem>
          <EuiFlexItem grow={false}>
            <code>ends</code> = ends with
          </EuiFlexItem>
          <EuiFlexItem grow={false}>
            <code>contains</code> = includes
          </EuiFlexItem>
          <EuiFlexItem grow={false}>
            <code>regex</code> = regular expression
          </EuiFlexItem>
          <EuiFlexItem grow={false}>
            <code>equals</code> = exact match
          </EuiFlexItem>
        </EuiFlexGroup>
      </EuiText>
    </div>
  );
}

/**
 * Field descriptions for common extraction fields
 */
const FIELD_DESCRIPTIONS = {
  article_title: 'Main headline extracted from h1 or article header',
  article_author: 'Author name from byline or author element',
  publish_date: 'Publication date from time element or date class',
  article_body: 'Main content area of the article',
  article_tags: 'Tags/categories as an array for filtering',
  product_name: 'Product title from heading or schema.org',
  product_price: 'Current price from price element',
  product_description: 'Product description text',
  product_sku: 'Stock keeping unit / product ID',
  doc_title: 'Documentation page title',
  doc_content: 'Main documentation content',
  page_title: 'Generic page title from h1',
  page_content: 'Main page content area',
};

/**
 * Output-related fields that should be excluded from user-facing config
 * These are runtime concerns set by the crawl execution environment
 */
const OUTPUT_FIELDS = ['output_sink', 'output_dir', 'output_index'];

/**
 * Filter output-related fields from config object
 * @param {Object} config - The full config object
 * @returns {Object} Config without output fields
 */
function filterOutputFields(config) {
  if (!config) return config;
  const filtered = { ...config };
  OUTPUT_FIELDS.forEach(field => delete filtered[field]);
  return filtered;
}

/**
 * Filter output-related lines from YAML content
 * @param {string} yamlContent - The full YAML string
 * @returns {string} YAML without output field lines
 */
function filterOutputFromYaml(yamlContent) {
  if (!yamlContent) return yamlContent;
  const lines = yamlContent.split('\n');
  const filtered = lines.filter(line => {
    const trimmed = line.trim();
    // Skip lines that start with output_ fields (top-level only)
    return !OUTPUT_FIELDS.some(field => trimmed.startsWith(`${field}:`));
  });
  return filtered.join('\n');
}

/**
 * Main ConfigPreview Component
 */
export default function ConfigPreview({ 
  yamlContent, 
  config, 
  sampleDocument,
  fieldMetadata,  // Suffix suggestions for extraction fields
  extractionPreview,  // NEW: Actual extracted values from validation
  extractionTestSummary,  // NEW: Summary of extraction test results
  validationWarnings,  // NEW: Warnings from workflow validation
  onDownload,
  onRunTest,
  onUseAndRun,  // New prop: callback to populate config in Run tab and switch to it
  onConfigChange, // New prop: callback when config is edited (passes updated config object)
}) {
  const [selectedTab, setSelectedTab] = useState('yaml');
  const [copySuccess, setCopySuccess] = useState(false);
  
  // Filter output fields from config and YAML for display
  // Output configuration is a runtime concern set by the crawl execution environment
  const displayYaml = filterOutputFromYaml(yamlContent);
  const displayConfig = filterOutputFields(config);
  
  // Editable YAML state
  const [editedYaml, setEditedYaml] = useState(displayYaml || '');
  const [isEdited, setIsEdited] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [isValidating, setIsValidating] = useState(false);
  const validationTimeoutRef = useRef(null);
  
  // Update editedYaml when new config is generated
  useEffect(() => {
    if (displayYaml) {
      setEditedYaml(displayYaml);
      setIsEdited(false);
      setValidationResult(null);
    }
  }, [displayYaml]);
  
  // Debounced validation on YAML change
  const validateYaml = useCallback(async (yamlString) => {
    if (!yamlString || yamlString.trim() === '') {
      setValidationResult({ valid: false, errors: ['Config is empty'] });
      return;
    }
    
    setIsValidating(true);
    
    try {
      // Parse YAML to JSON for API
      // Using a simple YAML parser approach - the API accepts config dict
      const response = await fetch(`${API_BASE}/extraction/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ yaml_content: yamlString }),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        setValidationResult({
          valid: false,
          errors: [errorData.detail || `Validation failed: ${response.status}`],
        });
        return;
      }
      
      const result = await response.json();
      setValidationResult({
        valid: result.valid,
        errors: result.errors || [],
        warnings: result.warnings || [],
        crawlerAvailable: !result.raw_output?.includes('not available'),
      });
      
      // If valid and we have a callback, notify parent of the updated config
      if (result.valid && onConfigChange) {
        // Parse YAML to get config object (API should return parsed config)
        // For now, just notify that validation passed
      }
    } catch (err) {
      setValidationResult({
        valid: false,
        errors: [`Validation error: ${err.message}`],
      });
    } finally {
      setIsValidating(false);
    }
  }, [onConfigChange]);
  
  // Handle YAML edit with debounced validation
  const handleYamlChange = useCallback((newYaml) => {
    setEditedYaml(newYaml);
    setIsEdited(newYaml !== displayYaml);
    
    // Clear previous timeout
    if (validationTimeoutRef.current) {
      clearTimeout(validationTimeoutRef.current);
    }
    
    // Debounce validation (800ms)
    validationTimeoutRef.current = setTimeout(() => {
      validateYaml(newYaml);
    }, 800);
  }, [displayYaml, validateYaml]);
  
  // Manual validation trigger
  const handleValidate = useCallback(() => {
    if (validationTimeoutRef.current) {
      clearTimeout(validationTimeoutRef.current);
    }
    validateYaml(editedYaml);
  }, [editedYaml, validateYaml]);
  
  // Reset to original
  const handleReset = useCallback(() => {
    setEditedYaml(displayYaml || '');
    setIsEdited(false);
    setValidationResult(null);
  }, [displayYaml]);
  
  // Check if config is valid for running
  const isConfigValid = validationResult?.valid !== false || (!isEdited && config);
  const hasErrors = validationResult?.errors?.length > 0;
  
  /**
   * Download YAML as file (uses edited content if modified)
   */
  const handleDownload = useCallback(() => {
    const yamlToDownload = isEdited ? editedYaml : displayYaml;
    if (!yamlToDownload) return;
    
    // Generate filename from domain
    let filename = 'crawler-config.yml';
    if (displayConfig?.domains?.[0]?.url) {
      const domain = displayConfig.domains[0].url
        .replace(/https?:\/\//, '')
        .replace(/[^a-zA-Z0-9]/g, '-');
      filename = `${domain}-config.yml`;
    }
    
    // Create blob and download
    const blob = new Blob([yamlToDownload], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    if (onDownload) onDownload();
  }, [isEdited, editedYaml, displayYaml, displayConfig, onDownload]);
  
  /**
   * Handle copy success feedback
   */
  const handleCopySuccess = useCallback(() => {
    setCopySuccess(true);
    setTimeout(() => setCopySuccess(false), 2000);
  }, []);
  
  // Extract config metadata from filtered config
  const extractedFields = [];
  if (displayConfig?.domains?.[0]?.extraction_rulesets) {
    for (const ruleset of displayConfig.domains[0].extraction_rulesets) {
      for (const rule of ruleset.rules || []) {
        if (rule.field_name) {
          extractedFields.push({
            name: rule.field_name,
            selector: rule.selector,
            joinAs: rule.join_as,
            description: FIELD_DESCRIPTIONS[rule.field_name],
          });
        }
      }
    }
  }
  
  const crawlRules = displayConfig?.domains?.[0]?.crawl_rules || [];
  const crawlRulesCount = crawlRules.length;
  
  // Count matched fields from extraction preview
  const extractionPreviewCount = extractionPreview ? Object.keys(extractionPreview).length : 0;
  const extractionMatchedCount = extractionPreview 
    ? Object.values(extractionPreview).filter(f => f.matched).length 
    : 0;
  
  // Tabs with edit indicator
  const tabs = [
    { 
      id: 'yaml', 
      name: isEdited ? 'YAML Config (edited)' : 'YAML Config', 
      badge: isEdited ? <EuiBadge color="warning">Modified</EuiBadge> : 
             (validationResult?.valid === false ? <EuiBadge color="danger">Invalid</EuiBadge> : null),
    },
    { id: 'crawl', name: `Crawl Rules (${crawlRulesCount})` },
    { id: 'fields', name: `Extraction Fields (${extractedFields.length})` },
    { 
      id: 'extraction', 
      name: 'Extraction Preview',
      badge: extractionPreview ? (
        <EuiBadge color={extractionMatchedCount === extractionPreviewCount ? 'success' : 'warning'}>
          {extractionMatchedCount}/{extractionPreviewCount}
        </EuiBadge>
      ) : null,
    },
    { id: 'sample', name: 'Sample Document' },
  ];
  
  return (
    <EuiPanel paddingSize="l">
      {/* Header */}
      <EuiFlexGroup justifyContent="spaceBetween" alignItems="center">
        <EuiFlexItem grow={false}>
          <EuiTitle size="s">
            <h3>Configuration Preview</h3>
          </EuiTitle>
        </EuiFlexItem>
        
        <EuiFlexItem grow={false}>
          <EuiFlexGroup gutterSize="s">
            {/* Reset button (only shown when edited) */}
            {isEdited && (
              <EuiFlexItem grow={false}>
                <EuiButtonEmpty
                  iconType="refresh"
                  onClick={handleReset}
                  size="s"
                  color="warning"
                >
                  Reset
                </EuiButtonEmpty>
              </EuiFlexItem>
            )}
            
            {/* Validate button */}
            <EuiFlexItem grow={false}>
              <EuiButtonEmpty
                iconType="check"
                onClick={handleValidate}
                disabled={!editedYaml || isValidating}
                size="s"
                isLoading={isValidating}
              >
                Validate
              </EuiButtonEmpty>
            </EuiFlexItem>
            
            {/* Copy button */}
            <EuiFlexItem grow={false}>
              <EuiCopy textToCopy={isEdited ? editedYaml : displayYaml || ''} afterMessage="Copied!">
                {(copy) => (
                  <EuiButtonEmpty
                    iconType={copySuccess ? 'check' : 'copy'}
                    onClick={() => {
                      copy();
                      handleCopySuccess();
                    }}
                    disabled={!editedYaml && !displayYaml}
                    size="s"
                  >
                    {copySuccess ? 'Copied!' : 'Copy'}
                  </EuiButtonEmpty>
                )}
              </EuiCopy>
            </EuiFlexItem>
            
            {/* Download button */}
            <EuiFlexItem grow={false}>
              <EuiButton
                iconType="download"
                onClick={handleDownload}
                disabled={!editedYaml && !displayYaml}
                size="s"
              >
                Download YAML
              </EuiButton>
            </EuiFlexItem>
            
            {/* Test button */}
            {onRunTest && (
              <EuiFlexItem grow={false}>
                <EuiButton
                  iconType="play"
                  onClick={onRunTest}
                  disabled={!config || hasErrors}
                  size="s"
                >
                  Test Extraction
                </EuiButton>
              </EuiFlexItem>
            )}
            
            {/* Use & Run button */}
            {onUseAndRun && (
              <EuiFlexItem grow={false}>
                <EuiToolTip
                  content={hasErrors ? "Fix validation errors before running" : "Use this config in the Run tab"}
                >
                  <EuiButton
                    iconType="play"
                    onClick={onUseAndRun}
                    disabled={!config || hasErrors}
                    size="s"
                    fill
                    color="success"
                  >
                    Use Config & Run
                  </EuiButton>
                </EuiToolTip>
              </EuiFlexItem>
            )}
          </EuiFlexGroup>
        </EuiFlexItem>
      </EuiFlexGroup>
      
      <EuiSpacer size="m" />
      
      {/* Config Summary */}
      {displayConfig && (
        <>
          <EuiFlexGroup gutterSize="m">
            <EuiFlexItem grow={false}>
              <EuiBadge color="primary">
                <EuiIcon type="globe" size="s" /> {displayConfig.domains?.[0]?.url}
              </EuiBadge>
            </EuiFlexItem>
            <EuiFlexItem grow={false}>
              <EuiBadge color="hollow">
                {crawlRulesCount} crawl rules
              </EuiBadge>
            </EuiFlexItem>
            <EuiFlexItem grow={false}>
              <EuiBadge color="hollow">
                {extractedFields.length} extraction fields
              </EuiBadge>
            </EuiFlexItem>
          </EuiFlexGroup>
          
          <EuiSpacer size="m" />
        </>
      )}
      
      {/* Validation Warnings from Workflow */}
      {validationWarnings && validationWarnings.length > 0 && (
        <>
          <EuiCallOut 
            color="warning" 
            iconType="warning" 
            title={`${validationWarnings.length} validation warning${validationWarnings.length !== 1 ? 's' : ''}`}
          >
            <EuiText size="s">
              <p>These warnings were detected during config validation. The config should still work, but you may want to review:</p>
              <ul style={{ margin: '8px 0 0 0', paddingLeft: '20px' }}>
                {validationWarnings.map((warn, i) => (
                  <li key={i}>{warn}</li>
                ))}
              </ul>
            </EuiText>
          </EuiCallOut>
          <EuiSpacer size="m" />
        </>
      )}
      
      {/* Tabs */}
      <EuiTabs>
        {tabs.map((tab) => (
          <EuiTab
            key={tab.id}
            isSelected={selectedTab === tab.id}
            onClick={() => setSelectedTab(tab.id)}
            append={tab.badge}
          >
            {tab.name}
          </EuiTab>
        ))}
      </EuiTabs>
      
      <EuiSpacer size="m" />
      
      {/* Tab Content */}
      {selectedTab === 'yaml' && (
        <>
          {/* Editable YAML Editor */}
          <YamlEditor 
            content={editedYaml} 
            onChange={handleYamlChange}
            disabled={false}
          />
          
          <EuiSpacer size="m" />
          
          {/* Validation Results */}
          <ValidationResults 
            result={validationResult} 
            isValidating={isValidating}
          />
          
          {/* Edit hint */}
          {!isEdited && !validationResult && (
            <EuiCallOut color="primary" iconType="iInCircle" size="s">
              <EuiText size="s">
                You can edit the YAML above. Changes will be validated automatically.
              </EuiText>
            </EuiCallOut>
          )}
        </>
      )}
      
      {selectedTab === 'crawl' && (
        <CrawlRulesDisplay rules={crawlRules} />
      )}
      
      {selectedTab === 'fields' && (
        <EuiPanel color="subdued" paddingSize="m">
          {extractedFields.length === 0 ? (
            <EuiText color="subdued" size="s">
              No extraction fields configured.
            </EuiText>
          ) : (
            <>
              {/* Info about default fields */}
              <EuiCallOut
                color="success"
                iconType="check"
                title="Default Fields Extracted Automatically"
                size="s"
                style={{ marginBottom: '12px' }}
              >
                <EuiText size="xs">
                  <p style={{ margin: 0 }}>
                    Open Crawler automatically extracts standard fields: <strong>title</strong>, <strong>body</strong>, <strong>url</strong>, <strong>meta_description</strong>, <strong>links</strong>, and more.
                    The fields below are <em>additional</em> custom extractions for site-specific content.
                  </p>
                </EuiText>
              </EuiCallOut>
              
              {/* Info about suffixes and editing */}
              <EuiCallOut
                color="primary"
                iconType="iInCircle"
                title="Field Naming Conventions"
                size="s"
                style={{ marginBottom: '16px' }}
              >
                <EuiText size="xs">
                  <p>
                    Field names use suffixes to control Elasticsearch mapping:{' '}
                    <strong>_semantic</strong> (AI search), <strong>_text</strong> (full-text), 
                    <strong>_keyword</strong> (exact match), <strong>_date</strong>, <strong>_num</strong>.
                  </p>
                  <p style={{ marginTop: '8px', marginBottom: 0 }}>
                    <strong>Want to change field names?</strong> Edit the YAML directly in the{' '}
                    <EuiButtonEmpty
                      size="xs"
                      onClick={() => setSelectedTab('yaml')}
                      style={{ padding: 0, height: 'auto' }}
                    >
                      YAML Config tab
                    </EuiButtonEmpty>
                    , then click <strong>Validate</strong> to check your changes.
                  </p>
                </EuiText>
              </EuiCallOut>
              
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #D3DAE6' }}>
                    <th style={{ textAlign: 'left', padding: '8px 12px' }}>Field Name</th>
                    <th style={{ textAlign: 'left', padding: '8px 12px' }}>Suffix</th>
                    <th style={{ textAlign: 'left', padding: '8px 12px' }}>Selector</th>
                    <th style={{ textAlign: 'left', padding: '8px 12px' }}>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {extractedFields.map((field, idx) => {
                    // Find matching metadata for this field
                    const meta = fieldMetadata?.find(m => m.field_name === field.name) || {};
                    return (
                      <tr key={idx} style={{ borderBottom: '1px solid #EEF2F7' }}>
                        <td style={{ padding: '8px 12px' }}>
                          <EuiCode>{field.name}</EuiCode>
                        </td>
                        <td style={{ padding: '8px 12px' }}>
                          {meta.suggested_suffix ? (
                            <EuiToolTip content={meta.suffix_reason || 'Recommended suffix'}>
                              <EuiBadge 
                                color={
                                  meta.suggested_suffix === '_semantic' ? 'accent' :
                                  meta.suggested_suffix === '_text' ? 'primary' :
                                  meta.suggested_suffix === '_keyword' ? 'warning' :
                                  meta.suggested_suffix === '_date' ? 'success' :
                                  meta.suggested_suffix?.includes('_num') ? 'hollow' :
                                  'default'
                                }
                              >
                                {meta.suggested_suffix}
                              </EuiBadge>
                            </EuiToolTip>
                          ) : (
                            <EuiText size="xs" color="subdued">—</EuiText>
                          )}
                        </td>
                        <td style={{ padding: '8px 12px', fontFamily: 'monospace', fontSize: '12px' }}>
                          <EuiToolTip content={field.selector || ''}>
                            <span>
                              {field.selector?.substring(0, 40)}
                              {field.selector?.length > 40 && '...'}
                            </span>
                          </EuiToolTip>
                        </td>
                        <td style={{ padding: '8px 12px' }}>
                          <EuiBadge color={field.joinAs === 'array' ? 'primary' : 'hollow'}>
                            {field.joinAs}
                          </EuiBadge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              
              {/* Suffix legend */}
              <EuiSpacer size="m" />
              <EuiFlexGroup gutterSize="s" wrap>
                <EuiFlexItem grow={false}>
                  <EuiBadge color="accent">_semantic</EuiBadge>
                  <EuiText size="xs" color="subdued"> AI/conceptual search</EuiText>
                </EuiFlexItem>
                <EuiFlexItem grow={false}>
                  <EuiBadge color="primary">_text</EuiBadge>
                  <EuiText size="xs" color="subdued"> Full-text search</EuiText>
                </EuiFlexItem>
                <EuiFlexItem grow={false}>
                  <EuiBadge color="warning">_keyword</EuiBadge>
                  <EuiText size="xs" color="subdued"> Exact match/filter</EuiText>
                </EuiFlexItem>
                <EuiFlexItem grow={false}>
                  <EuiBadge color="success">_date</EuiBadge>
                  <EuiText size="xs" color="subdued"> Date ranges</EuiText>
                </EuiFlexItem>
                <EuiFlexItem grow={false}>
                  <EuiBadge color="hollow">_num</EuiBadge>
                  <EuiText size="xs" color="subdued"> Numbers</EuiText>
                </EuiFlexItem>
              </EuiFlexGroup>
            </>
          )}
        </EuiPanel>
      )}
      
      {selectedTab === 'extraction' && (
        <EuiPanel color="subdued" paddingSize="m">
          <EuiTitle size="xs">
            <h4>Extraction Test Results</h4>
          </EuiTitle>
          <EuiText size="s" color="subdued">
            <p>These values were extracted during config validation by testing the selectors against actual page content.</p>
          </EuiText>
          <EuiSpacer size="m" />
          
          {extractionTestSummary && (
            <>
              <EuiCallOut
                color={extractionTestSummary.fields_failed === 0 ? 'success' : 'warning'}
                iconType={extractionTestSummary.fields_failed === 0 ? 'check' : 'alert'}
                title={`${extractionTestSummary.fields_matched} of ${extractionTestSummary.total_fields} fields matched`}
                size="s"
              />
              <EuiSpacer size="m" />
            </>
          )}
          
          {extractionPreview ? (
            <div style={{ 
              backgroundColor: '#1D1E24', 
              borderRadius: '6px', 
              padding: '16px',
              maxHeight: '400px',
              overflow: 'auto',
            }}>
              {Object.entries(extractionPreview).map(([fieldName, fieldData]) => (
                <div key={fieldName} style={{ marginBottom: '16px' }}>
                  <EuiFlexGroup gutterSize="s" alignItems="center">
                    <EuiFlexItem grow={false}>
                      <EuiIcon 
                        type={fieldData.matched ? 'check' : 'cross'} 
                        color={fieldData.matched ? 'success' : 'danger'} 
                      />
                    </EuiFlexItem>
                    <EuiFlexItem grow={false}>
                      <EuiText size="s" style={{ color: '#98C379', fontFamily: 'monospace' }}>
                        {fieldName}
                      </EuiText>
                    </EuiFlexItem>
                    <EuiFlexItem grow={false}>
                      <EuiText size="xs" color="subdued" style={{ fontFamily: 'monospace' }}>
                        ({fieldData.selector})
                      </EuiText>
                    </EuiFlexItem>
                  </EuiFlexGroup>
                  <div style={{ 
                    marginLeft: '24px', 
                    marginTop: '4px',
                    padding: '8px',
                    backgroundColor: '#282C34',
                    borderRadius: '4px',
                    fontFamily: 'monospace',
                    fontSize: '12px',
                    color: fieldData.matched ? '#DFE5EF' : '#6B7280',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}>
                    {fieldData.value || '(no value extracted)'}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EuiCallOut
              color="primary"
              iconType="iInCircle"
              title="No extraction preview available"
            >
              <p>Run a full config generation to see extraction results.</p>
            </EuiCallOut>
          )}
        </EuiPanel>
      )}
      
      {selectedTab === 'sample' && (
        <SampleDocumentPreview document={sampleDocument} />
      )}
    </EuiPanel>
  );
}
