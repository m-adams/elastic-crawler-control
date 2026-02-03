/**
 * ConfigGenerator Component
 * 
 * Chat-like interface for generating Open Crawler configurations.
 * Uses SSE streaming from /api/generate endpoint.
 * 
 * Features:
 * - Debounced URL preflight validation (no LLM required)
 * - Real-time phase progress indicators
 * - SSE streaming of workflow events
 * - Firecrawl recommendation for bot-protected sites
 * - Final config preview with copy/download
 * 
 * @see hive-mind/patterns/elastic/STREAMING_CHAT_UI_PATTERNS.md
 */

import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import {
  EuiPanel,
  EuiFlexGroup,
  EuiFlexItem,
  EuiFieldText,
  EuiFieldPassword,
  EuiTextArea,
  EuiButton,
  EuiButtonEmpty,
  EuiProgress,
  EuiText,
  EuiSpacer,
  EuiCallOut,
  EuiAccordion,
  EuiCode,
  EuiIcon,
  EuiLoadingSpinner,
  EuiBadge,
  EuiFormRow,
  EuiLink,
  EuiToolTip,
  EuiHorizontalRule,
  EuiPopover,
  EuiSelect,
} from '@elastic/eui';
import SiteDirectory, { SiteSuggestions } from './SiteDirectory';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

// Debounce hook
function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value);
  
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);
    
    return () => clearTimeout(handler);
  }, [value, delay]);
  
  return debouncedValue;
}

// Workflow phases in order
const PHASES = [
  { id: 'preflight', label: 'Pre-flight', icon: 'globe' },
  { id: 'deep_check', label: 'Deep Check', icon: 'inspect' },
  { id: 'investigating', label: 'Site Investigation', icon: 'search' },
  { id: 'generating', label: 'Config Generation', icon: 'document' },
  { id: 'validating', label: 'Validation', icon: 'check' },
  { id: 'complete', label: 'Complete', icon: 'checkInCircleFilled' },
];

/**
 * Phase Progress Indicator
 * Shows progress through workflow phases
 */
function PhaseProgress({ currentPhase, iterationCount }) {
  const phaseIndex = PHASES.findIndex(p => p.id === currentPhase);
  
  return (
    <EuiFlexGroup alignItems="center" gutterSize="s">
      {PHASES.map((phase, idx) => {
        const isActive = phase.id === currentPhase;
        const isComplete = idx < phaseIndex || currentPhase === 'complete';
        const isPending = idx > phaseIndex && currentPhase !== 'complete';
        
        return (
          <EuiFlexItem grow={false} key={phase.id}>
            <EuiFlexGroup alignItems="center" gutterSize="xs">
              <EuiFlexItem grow={false}>
                {isActive && currentPhase !== 'complete' ? (
                  <EuiLoadingSpinner size="s" />
                ) : (
                  <EuiIcon 
                    type={phase.icon} 
                    color={isComplete ? 'success' : isPending ? 'subdued' : 'primary'}
                  />
                )}
              </EuiFlexItem>
              <EuiFlexItem grow={false}>
                <EuiText 
                  size="xs" 
                  color={isActive ? 'default' : isPending ? 'subdued' : 'success'}
                >
                  {phase.label}
                  {phase.id === 'validating' && iterationCount > 1 && (
                    <EuiBadge color="warning" style={{ marginLeft: 4 }}>
                      Retry {iterationCount}
                    </EuiBadge>
                  )}
                </EuiText>
              </EuiFlexItem>
              {idx < PHASES.length - 1 && (
                <EuiFlexItem grow={false}>
                  <EuiIcon type="arrowRight" color="subdued" size="s" />
                </EuiFlexItem>
              )}
            </EuiFlexGroup>
          </EuiFlexItem>
        );
      })}
    </EuiFlexGroup>
  );
}

/**
 * Event Log Entry
 * Displays a single workflow event
 */
function EventEntry({ event, isLatest }) {
  // Determine event type and style
  let color = 'subdued';
  let icon = 'dot';
  let label = 'Event';
  
  if (event.phase) {
    const phaseMap = {
      preflight: { color: 'primary', icon: 'globe', label: 'Preflight' },
      deep_check: { color: 'primary', icon: 'inspect', label: 'Deep Check' },
      starting_workflow: { color: 'primary', icon: 'playFilled', label: 'Starting' },
      investigating: { color: 'primary', icon: 'search', label: 'Investigation' },
      generating: { color: 'accent', icon: 'document', label: 'Generation' },
      validating: { color: 'warning', icon: 'checkInCircleFilled', label: 'Validation' },
      iterating: { color: 'warning', icon: 'refresh', label: 'Iteration' },
      complete: { color: 'success', icon: 'checkInCircleFilled', label: 'Complete' },
      blocked: { color: 'warning', icon: 'iInCircle', label: 'Blocked' },
      error: { color: 'danger', icon: 'crossInCircleFilled', label: 'Error' },
    };
    const phaseInfo = phaseMap[event.phase] || {};
    color = phaseInfo.color || color;
    icon = phaseInfo.icon || icon;
    label = phaseInfo.label || label;
  }
  
  if (event.error) {
    color = 'danger';
    icon = 'error';
    label = 'Error';
  }
  
  return (
    <EuiFlexGroup 
      alignItems="flexStart" 
      gutterSize="s"
      style={{ 
        opacity: isLatest ? 1 : 0.7,
        marginBottom: 8,
      }}
    >
      <EuiFlexItem grow={false}>
        <EuiIcon type={icon} color={color} />
      </EuiFlexItem>
      <EuiFlexItem>
        <EuiText size="xs">
          <strong>{label}</strong>
          {event.message && <span>: {event.message}</span>}
          {event.content && typeof event.content === 'string' && (
            <span>: {event.content.substring(0, 100)}...</span>
          )}
          {event.error && <span style={{ color: '#BD271E' }}>: {event.error}</span>}
        </EuiText>
      </EuiFlexItem>
    </EuiFlexGroup>
  );
}

/**
 * Main ConfigGenerator Component
 */
// LLM Proxy signup URL
const LLM_PROXY_SIGNUP_URL = "https://litellm-proxy-service-1059491012611.us-central1.run.app";

/**
 * Preflight Status Display
 * Shows URL validation results as user types
 */
function PreflightStatus({ preflight, isChecking }) {
  if (!preflight && !isChecking) return null;
  
  if (isChecking) {
    return (
      <EuiFlexGroup alignItems="center" gutterSize="xs">
        <EuiFlexItem grow={false}>
          <EuiLoadingSpinner size="s" />
        </EuiFlexItem>
        <EuiFlexItem>
          <EuiText size="xs" color="subdued">Checking domain...</EuiText>
        </EuiFlexItem>
      </EuiFlexGroup>
    );
  }
  
  if (!preflight) return null;
  
  const checks = [
    { key: 'url_valid', label: 'URL format', ok: preflight.url_valid },
    { key: 'dns_resolves', label: 'DNS resolves', ok: preflight.dns_resolves },
    { key: 'http_reachable', label: 'Site reachable', ok: preflight.http_reachable },
  ];
  
  // Add robots.txt info
  if (preflight.robots_txt) {
    const robotsOk = preflight.robots_txt.allows_crawling !== false;
    checks.push({
      key: 'robots',
      label: robotsOk ? 'Crawling allowed' : 'robots.txt blocks crawling',
      ok: robotsOk,
      isWarning: !robotsOk,
    });
  }
  
  return (
    <EuiFlexGroup gutterSize="m" alignItems="center" wrap>
      {checks.map(check => (
        <EuiFlexItem grow={false} key={check.key}>
          <EuiFlexGroup alignItems="center" gutterSize="xs">
            <EuiFlexItem grow={false}>
              <EuiIcon 
                type={check.ok ? 'checkInCircleFilled' : 'crossInCircleFilled'} 
                color={check.ok ? 'success' : check.isWarning ? 'warning' : 'danger'} 
                size="s"
              />
            </EuiFlexItem>
            <EuiFlexItem grow={false}>
              <EuiText size="xs" color={!check.ok && !check.isWarning ? 'danger' : 'subdued'}>
                {check.label}
              </EuiText>
            </EuiFlexItem>
          </EuiFlexGroup>
        </EuiFlexItem>
      ))}
      {preflight.response_time_ms && (
        <EuiFlexItem grow={false}>
          <EuiText size="xs" color="subdued">({preflight.response_time_ms}ms)</EuiText>
        </EuiFlexItem>
      )}
    </EuiFlexGroup>
  );
}

/**
 * Firecrawl Recommendation Banner
 */
function FirecrawlBanner({ firecrawlInfo, reason }) {
  if (!firecrawlInfo) return null;
  
  return (
    <EuiCallOut
      title="Consider using Firecrawl"
      color="warning"
      iconType="iInCircle"
    >
      <EuiText size="s">
        <p><strong>Reason:</strong> {reason}</p>
        <p>{firecrawlInfo.description}</p>
        <p><strong>Note:</strong> {firecrawlInfo.pricing_note}</p>
        <EuiSpacer size="s" />
        <EuiLink href={firecrawlInfo.url} target="_blank" external>
          Learn more about Firecrawl
        </EuiLink>
      </EuiText>
    </EuiCallOut>
  );
}

export default function ConfigGenerator({ onConfigGenerated }) {
  // Form state
  const [url, setUrl] = useState('');
  const [userContext, setUserContext] = useState('');
  const [outputSink, setOutputSink] = useState('file');
  
  // Site suggestions state
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedSite, setSelectedSite] = useState(null);
  const [siteDirectoryOpen, setSiteDirectoryOpen] = useState(false);
  
  // Debounced URL for preflight checks
  const debouncedUrl = useDebounce(url, 500);
  
  // Preflight state
  const [preflightResult, setPreflightResult] = useState(null);
  const [isCheckingPreflight, setIsCheckingPreflight] = useState(false);
  const [preflightError, setPreflightError] = useState(null);
  
  // Firecrawl recommendation state (from deep check during generation)
  const [firecrawlInfo, setFirecrawlInfo] = useState(null);
  const [firecrawlReason, setFirecrawlReason] = useState(null);
  
  // LLM API Key state
  const [llmApiKey, setLlmApiKey] = useState(() => {
    // Load from localStorage on initial render
    return localStorage.getItem('llm_api_key') || '';
  });
  const [isValidatingKey, setIsValidatingKey] = useState(false);
  const [keyValidation, setKeyValidation] = useState(null); // null, 'valid', 'invalid'
  const [keyValidationMessage, setKeyValidationMessage] = useState('');
  
  // Workflow state
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentPhase, setCurrentPhase] = useState(null);
  const [iterationCount, setIterationCount] = useState(0);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);
  
  // Results
  const [yamlContent, setYamlContent] = useState(null);
  const [config, setConfig] = useState(null);
  const [investigationSummary, setInvestigationSummary] = useState(null);
  const [sampleDocument, setSampleDocument] = useState(null);
  const [fieldMetadata, setFieldMetadata] = useState(null);
  const [extractionPreview, setExtractionPreview] = useState(null);
  const [extractionTestSummary, setExtractionTestSummary] = useState(null);
  const [validationWarnings, setValidationWarnings] = useState([]);
  
  // Content type for guiding extraction
  const [contentType, setContentType] = useState('');
  
  // Refs
  const abortRef = useRef(null);
  const eventLogRef = useRef(null);
  
  // Run preflight check when URL changes (debounced)
  useEffect(() => {
    const checkPreflight = async () => {
      if (!debouncedUrl || debouncedUrl.length < 5) {
        setPreflightResult(null);
        setPreflightError(null);
        setFirecrawlInfo(null);
        return;
      }
      
      setIsCheckingPreflight(true);
      setPreflightError(null);
      
      try {
        const response = await fetch(`${API_BASE}/domain/preflight`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: debouncedUrl }),
        });
        
        if (response.ok) {
          const result = await response.json();
          setPreflightResult(result);
        } else {
          setPreflightError('Failed to check domain');
        }
      } catch (err) {
        setPreflightError(err.message);
      } finally {
        setIsCheckingPreflight(false);
      }
    };
    
    checkPreflight();
  }, [debouncedUrl]);
  
  // Compute if we can proceed with generation
  const canGenerate = useMemo(() => {
    if (!url.trim() || !llmApiKey.trim()) return false;
    if (isCheckingPreflight) return false;
    if (preflightResult && !preflightResult.viable_for_crawling) return false;
    return true;
  }, [url, llmApiKey, isCheckingPreflight, preflightResult]);
  
  // Compute if we can create a quick config (no LLM needed)
  const canCreateQuickConfig = useMemo(() => {
    if (!url.trim()) return false;
    if (isCheckingPreflight) return false;
    if (preflightResult && !preflightResult.viable_for_crawling) return false;
    if (preflightResult && preflightResult.viable_for_crawling) return true;
    return false;
  }, [url, isCheckingPreflight, preflightResult]);
  
  /**
   * Create a basic config without LLM
   * Uses preflight data (sitemaps, domain info) to build a template
   */
  const handleQuickConfig = useCallback(() => {
    if (!preflightResult) return;
    
    // Build basic config from preflight data
    const domain = preflightResult.final_url || preflightResult.normalized_url;
    
    // Get seed URLs from sitemaps if available
    const sitemaps = preflightResult.robots_txt?.sitemap_urls || [];
    
    // Create basic config
    const quickConfig = {
      domains: [
        {
          url: domain,
          // If we have sitemaps, include first few as seed URLs
          ...(sitemaps.length > 0 && { seed_urls: sitemaps.slice(0, 3) }),
        }
      ],
      max_crawl_depth: 2,
      max_unique_url_count: 100,
      output_index: preflightResult.domain.replace(/\./g, '-') + '-crawl',
    };
    
    // Generate simple YAML
    const yamlContent = `# Quick Config for ${domain}
# Generated without AI - customize extraction rules as needed

domains:
  - url: "${domain}"
${sitemaps.length > 0 ? `    seed_urls:
${sitemaps.slice(0, 3).map(s => `      - "${s}"`).join('\n')}` : ''}

max_crawl_depth: 2
max_unique_url_count: 100
output_index: "${quickConfig.output_index}"

# Add extraction rules manually or use AI generation
# extraction_rules:
#   - name: example_field
#     selector: ".css-selector"
#     source: content
`;
    
    // Call the callback with the quick config
    if (onConfigGenerated) {
      onConfigGenerated({
        yaml: yamlContent,
        config: quickConfig,
        sampleDocument: null,
      });
    }
    
    // Show success
    setCurrentPhase('complete');
    setYamlContent(yamlContent);
    setConfig(quickConfig);
  }, [preflightResult, onConfigGenerated]);
  
  // Auto-scroll event log
  useEffect(() => {
    if (eventLogRef.current) {
      eventLogRef.current.scrollTop = eventLogRef.current.scrollHeight;
    }
  }, [events]);
  
  // Save API key to localStorage when it changes
  useEffect(() => {
    if (llmApiKey) {
      localStorage.setItem('llm_api_key', llmApiKey);
    }
  }, [llmApiKey]);
  
  // Track if initial validation has been attempted
  const initialValidationDone = useRef(false);
  
  // Notify parent when generation completes (fixes stale closure issue)
  useEffect(() => {
    if (currentPhase === 'complete' && yamlContent && config && onConfigGenerated) {
      onConfigGenerated({ 
        yaml: yamlContent, 
        config, 
        sampleDocument, 
        fieldMetadata,
        extractionPreview,
        extractionTestSummary,
        validationWarnings,
      });
    }
  }, [currentPhase, yamlContent, config, sampleDocument, fieldMetadata, extractionPreview, extractionTestSummary, validationWarnings, onConfigGenerated]);
  
  /**
   * Validate the LLM API key
   */
  const validateApiKey = useCallback(async () => {
    if (!llmApiKey.trim()) {
      setKeyValidation('invalid');
      setKeyValidationMessage('API key is required');
      return false;
    }
    
    setIsValidatingKey(true);
    setKeyValidation(null);
    
    try {
      const response = await fetch(`${API_BASE}/validate-key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: llmApiKey.trim() }),
      });
      
      const result = await response.json();
      
      if (result.valid) {
        setKeyValidation('valid');
        setKeyValidationMessage('API key is valid');
        return true;
      } else {
        setKeyValidation('invalid');
        setKeyValidationMessage(result.message || 'Invalid API key');
        return false;
      }
    } catch (err) {
      setKeyValidation('invalid');
      setKeyValidationMessage(`Validation failed: ${err.message}`);
      return false;
    } finally {
      setIsValidatingKey(false);
    }
  }, [llmApiKey]);
  
  // Auto-validate API key on page load if one exists
  // (Must be after validateApiKey is defined)
  useEffect(() => {
    if (llmApiKey && !initialValidationDone.current) {
      initialValidationDone.current = true;
      // Delay slightly to avoid validation during initial render
      const timer = setTimeout(() => {
        validateApiKey();
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [llmApiKey, validateApiKey]);
  
  /**
   * Parse SSE event data
   */
  const parseEvent = useCallback((eventData) => {
    try {
      // Handle nested data structures from Agno
      let data = eventData;
      if (data.data && typeof data.data === 'object') {
        data = data.data;
      }
      
      // Extract phase from content
      if (data.content && typeof data.content === 'object') {
        const content = data.content;
        
        if (content.phase) {
          setCurrentPhase(content.phase);
          
          // Handle blocked phase (Firecrawl recommendation)
          if (content.phase === 'blocked') {
            if (content.firecrawl) {
              setFirecrawlInfo(content.firecrawl);
              setFirecrawlReason(content.blocked_reason || content.firecrawl.reason);
            }
            setError(content.message || 'Site not suitable for Open Crawler');
          }
        }
        
        if (content.iteration_count) {
          setIterationCount(content.iteration_count);
        }
        
        // Store investigation results
        if (content.investigation_result) {
          setInvestigationSummary(content.investigation_result);
        }
        
        // Store config results
        if (content.config_result) {
          if (content.config_result.yaml_content) {
            setYamlContent(content.config_result.yaml_content);
          }
          if (content.config_result.config) {
            setConfig(content.config_result.config);
          }
          if (content.config_result.sample_document) {
            setSampleDocument(content.config_result.sample_document);
          }
          if (content.config_result.field_metadata) {
            setFieldMetadata(content.config_result.field_metadata);
          }
        }
        
        // Final outputs
        if (content.final_yaml) {
          setYamlContent(content.final_yaml);
        }
        if (content.final_config) {
          setConfig(content.final_config);
        }
        
        // Extraction preview from validation (shows actual extracted values)
        if (content.extraction_preview) {
          setExtractionPreview(content.extraction_preview);
        }
        if (content.extraction_test_summary) {
          setExtractionTestSummary(content.extraction_test_summary);
        }
        
        // Capture validation warnings from workflow
        if (content.validation_result?.warnings) {
          setValidationWarnings(content.validation_result.warnings);
        }
        if (content.warnings) {
          setValidationWarnings(prev => [...prev, ...content.warnings]);
        }
        
        // Handle complete phase with yaml_content and config directly
        if (content.phase === 'complete') {
          if (content.yaml_content) {
            setYamlContent(content.yaml_content);
          }
          if (content.config) {
            setConfig(content.config);
          }
        }
        
        // Preflight failed
        if (content.preflight_failed) {
          setError(content.error || 'Domain pre-check failed');
        }
        
        // Error
        if (content.error && !content.firecrawl) {
          setError(content.error);
        }
      }
      
      // Add to event log
      return {
        timestamp: new Date().toISOString(),
        phase: data.content?.phase,
        message: data.content?.message || data.message,
        content: data.content,
        error: data.error,
      };
    } catch (e) {
      console.error('Error parsing event:', e, eventData);
      return {
        timestamp: new Date().toISOString(),
        error: 'Failed to parse event',
      };
    }
  }, []);
  
  /**
   * Start config generation with SSE streaming
   */
  const handleGenerate = useCallback(async () => {
    if (!url.trim()) {
      setError('Please enter a URL');
      return;
    }
    
    // Reset state
    setIsGenerating(true);
    setError(null);
    setEvents([]);
    setCurrentPhase('preflight'); // Start with preflight (matches backend)
    setIterationCount(0);
    setYamlContent(null);
    setConfig(null);
    setInvestigationSummary(null);
    setSampleDocument(null);
    setFieldMetadata(null);
    setExtractionPreview(null);
    setExtractionTestSummary(null);
    setValidationWarnings([]);
    
    // Create abort controller
    const abortController = new AbortController();
    abortRef.current = abortController;
    
    try {
      // Make request to /api/generate
      const response = await fetch(`${API_BASE}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          domain: url.trim(),
          user_context: userContext.trim() || undefined,
          content_type: contentType || undefined,
          output_sink: outputSink,
          llm_api_key: llmApiKey.trim() || undefined,
        }),
        signal: abortController.signal,
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      if (!response.body) {
        throw new Error('No response body - SSE not supported');
      }
      
      // Read SSE stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          // Skip empty lines and keepalive comments
          if (!line.trim() || line.startsWith(':')) continue;
          
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              const event = parseEvent(data);
              setEvents(prev => [...prev, event]);
            } catch (e) {
              console.warn('Failed to parse SSE data:', line);
            }
          }
        }
      }
      
      // Note: onConfigGenerated is called via useEffect when currentPhase becomes 'complete'
      // This avoids stale closure issues with React state
      
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message);
        setCurrentPhase('error');
      }
    } finally {
      setIsGenerating(false);
      abortRef.current = null;
    }
  }, [url, userContext, outputSink, llmApiKey, parseEvent]);
  
  /**
   * Cancel generation
   */
  const handleCancel = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      setIsGenerating(false);
      setCurrentPhase(null);
    }
  }, []);
  
  /**
   * Reset form
   */
  const handleReset = useCallback(() => {
    setUrl('');
    setUserContext('');
    setOutputSink('file');
    setContentType('');
    // Don't reset API key - keep it for convenience
    setIsGenerating(false);
    setCurrentPhase(null);
    setIterationCount(0);
    setEvents([]);
    setError(null);
    setYamlContent(null);
    setConfig(null);
    setInvestigationSummary(null);
    setSampleDocument(null);
    setFieldMetadata(null);
    setExtractionPreview(null);
    setExtractionTestSummary(null);
    setValidationWarnings([]);
    // Reset preflight and firecrawl state
    setPreflightResult(null);
    setPreflightError(null);
    setFirecrawlInfo(null);
    setFirecrawlReason(null);
    // Reset site selection
    setSelectedSite(null);
    setShowSuggestions(false);
  }, []);
  
  /**
   * Handle site selection from directory or suggestions
   */
  const handleSelectSite = useCallback((site) => {
    setUrl(site.url);
    setSelectedSite(site);
    setShowSuggestions(false);
    setSiteDirectoryOpen(false); // Collapse accordion to show form was filled
    // Pre-fill context based on content type
    if (site.content_type && !userContext) {
      const contextHints = {
        blog: 'Crawl blog/news articles for content indexing',
        documentation: 'Crawl documentation pages for search',
        ecommerce: 'Crawl product pages for catalog indexing',
      };
      if (contextHints[site.content_type]) {
        setUserContext(contextHints[site.content_type]);
      }
    }
  }, [userContext]);
  
  return (
    <EuiPanel paddingSize="l">
      {/* Header */}
      <EuiText>
        <h3>Generate Crawler Configuration</h3>
        <p>Enter a URL to automatically generate an optimized Open Crawler configuration.</p>
      </EuiText>
      
      <EuiSpacer size="m" />
      
      {/* Site Directory - Demo Sites */}
      <EuiAccordion
        id="siteDirectory"
        buttonContent={
          <EuiFlexGroup alignItems="center" gutterSize="s">
            <EuiFlexItem grow={false}>
              <EuiIcon type="list" />
            </EuiFlexItem>
            <EuiFlexItem grow={false}>
              <EuiText size="s">
                <strong>Demo Site Directory</strong>
              </EuiText>
            </EuiFlexItem>
            <EuiFlexItem grow={false}>
              <EuiBadge color="hollow">Pre-tested sites</EuiBadge>
            </EuiFlexItem>
          </EuiFlexGroup>
        }
        forceState={siteDirectoryOpen ? 'open' : 'closed'}
        onToggle={(isOpen) => setSiteDirectoryOpen(isOpen)}
        paddingSize="m"
      >
        <EuiSpacer size="s" />
        <SiteDirectory 
          onSelectSite={handleSelectSite}
          showHeader={false}
        />
      </EuiAccordion>
      
      <EuiSpacer size="m" />
      
      {/* LLM API Key Configuration */}
      <EuiAccordion
        id="llmConfig"
        buttonContent={
          <EuiFlexGroup alignItems="center" gutterSize="s">
            <EuiFlexItem grow={false}>
              <EuiIcon type="lock" />
            </EuiFlexItem>
            <EuiFlexItem grow={false}>
              <EuiText size="s">
                <strong>LLM API Key</strong>
                {keyValidation === 'valid' && (
                  <EuiBadge color="success" style={{ marginLeft: 8 }}>Valid</EuiBadge>
                )}
                {keyValidation === 'invalid' && (
                  <EuiBadge color="danger" style={{ marginLeft: 8 }}>Invalid</EuiBadge>
                )}
                {!llmApiKey && (
                  <EuiBadge color="hollow" style={{ marginLeft: 8 }}>Optional</EuiBadge>
                )}
              </EuiText>
            </EuiFlexItem>
          </EuiFlexGroup>
        }
        initialIsOpen={!llmApiKey}
        paddingSize="m"
      >
        <EuiSpacer size="s" />
        <EuiText size="xs" color="subdued">
          <p>
            An LLM API key is required for AI-powered config generation with smart extraction rules.{' '}
            <EuiLink href={LLM_PROXY_SIGNUP_URL} target="_blank" external>
              Get your API key here
            </EuiLink>
          </p>
          <p>
            <strong>No API key?</strong> Use "Quick Config" to create a basic config without AI.
          </p>
        </EuiText>
        <EuiSpacer size="s" />
        <EuiFlexGroup alignItems="flexEnd" gutterSize="s">
          <EuiFlexItem>
            <EuiFormRow
              label="API Key"
              helpText={keyValidationMessage || "Your key will be saved locally for convenience"}
              isInvalid={keyValidation === 'invalid'}
              fullWidth
            >
              <EuiFieldPassword
                placeholder="Enter your LLM Proxy API key"
                value={llmApiKey}
                onChange={(e) => {
                  setLlmApiKey(e.target.value);
                  setKeyValidation(null);
                  setKeyValidationMessage('');
                }}
                disabled={isGenerating}
                type="dual"
                fullWidth
              />
            </EuiFormRow>
          </EuiFlexItem>
          <EuiFlexItem grow={false}>
            <EuiButton
              onClick={validateApiKey}
              isLoading={isValidatingKey}
              disabled={!llmApiKey.trim() || isGenerating}
              size="m"
            >
              Validate
            </EuiButton>
          </EuiFlexItem>
        </EuiFlexGroup>
      </EuiAccordion>
      
      <EuiSpacer size="m" />
      
      {/* Input Form */}
      <EuiFlexGroup alignItems="flexEnd">
        <EuiFlexItem grow={3}>
          <EuiFormRow 
            label={
              <EuiFlexGroup alignItems="center" gutterSize="s" responsive={false}>
                <EuiFlexItem grow={false}>Website URL</EuiFlexItem>
                {selectedSite && (
                  <EuiFlexItem grow={false}>
                    <EuiBadge 
                      color={selectedSite.status === 'works' ? 'success' : selectedSite.status === 'partial' ? 'warning' : 'danger'}
                    >
                      {selectedSite.name}
                    </EuiBadge>
                  </EuiFlexItem>
                )}
              </EuiFlexGroup>
            }
            fullWidth
            isInvalid={preflightResult && !preflightResult.viable_for_crawling}
            error={preflightResult && !preflightResult.viable_for_crawling ? 
              preflightResult.issues?.find(i => i.severity === 'error')?.message : null
            }
          >
            <EuiPopover
              button={
                <EuiFieldText
                  placeholder="https://www.example.com (or start typing to see suggestions)"
                  value={url}
                  onChange={(e) => {
                    setUrl(e.target.value);
                    setSelectedSite(null); // Clear selected site when typing
                    setShowSuggestions(e.target.value.length >= 2);
                    setSiteDirectoryOpen(false); // Auto-close directory when user types
                  }}
                  onFocus={() => url.length >= 2 && setShowSuggestions(true)}
                  onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                  disabled={isGenerating}
                  fullWidth
                  prepend={<EuiIcon type="globe" />}
                  isInvalid={preflightResult && !preflightResult.viable_for_crawling}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && canGenerate && !isGenerating) {
                      handleGenerate();
                    }
                  }}
                />
              }
              isOpen={showSuggestions && url.length >= 2 && !isGenerating}
              closePopover={() => setShowSuggestions(false)}
              panelPaddingSize="none"
              anchorPosition="downLeft"
              hasArrow={false}
              repositionOnScroll
            >
              <SiteSuggestions 
                query={url} 
                onSelect={(site) => {
                  handleSelectSite(site);
                }}
                maxResults={5}
              />
            </EuiPopover>
          </EuiFormRow>
        </EuiFlexItem>
        
        <EuiFlexItem grow={false}>
          <EuiFlexGroup gutterSize="s">
            {isGenerating ? (
              <EuiFlexItem grow={false}>
                <EuiButton onClick={handleCancel} color="danger" iconType="cross">
                  Cancel
                </EuiButton>
              </EuiFlexItem>
            ) : (
              <>
                <EuiFlexItem grow={false}>
                  <EuiToolTip
                    content={
                      !llmApiKey.trim() ? "Please enter an LLM API key first" :
                      !canGenerate && preflightResult ? "Domain pre-check failed" : ""
                    }
                    position="top"
                  >
                    <EuiButton 
                      onClick={handleGenerate} 
                      fill 
                      iconType="sparkles"
                      disabled={!canGenerate}
                    >
                      Generate Config
                    </EuiButton>
                  </EuiToolTip>
                </EuiFlexItem>
                <EuiFlexItem grow={false}>
                  <EuiToolTip
                    content={canCreateQuickConfig ? "Create basic config without AI" : "Enter a valid URL first"}
                    position="top"
                  >
                    <EuiButton 
                      onClick={handleQuickConfig} 
                      iconType="document"
                      disabled={!canCreateQuickConfig}
                    >
                      Quick Config
                    </EuiButton>
                  </EuiToolTip>
                </EuiFlexItem>
              </>
            )}
          </EuiFlexGroup>
        </EuiFlexItem>
      </EuiFlexGroup>
      
      {/* Preflight Status (shown as user types) */}
      {(isCheckingPreflight || preflightResult) && (
        <>
          <EuiSpacer size="s" />
          <PreflightStatus preflight={preflightResult} isChecking={isCheckingPreflight} />
        </>
      )}
      
      <EuiSpacer size="m" />
      
      {/* Content Type Selection */}
      <EuiFlexGroup gutterSize="m">
        <EuiFlexItem grow={1}>
          <EuiFormRow 
            label="Content Type" 
            helpText="Guides extraction rules for this type of content"
          >
            <EuiSelect
              options={[
                { value: '', text: 'Auto-detect (recommended)' },
                { value: 'blog', text: 'Blog / News Articles' },
                { value: 'documentation', text: 'Documentation / Help Pages' },
                { value: 'ecommerce', text: 'E-commerce / Product Pages' },
                { value: 'general', text: 'General Website' },
              ]}
              value={contentType}
              onChange={(e) => setContentType(e.target.value)}
              disabled={isGenerating}
            />
          </EuiFormRow>
        </EuiFlexItem>
        <EuiFlexItem grow={2}>
          {/* User Context (Free-text) */}
          <EuiFormRow 
            label="Context / Goals" 
            helpText="Describe what you're trying to achieve (optional)"
          >
            <EuiTextArea
              placeholder="e.g., I want to crawl product pages to extract prices and descriptions for competitive analysis..."
              value={userContext}
              onChange={(e) => setUserContext(e.target.value)}
              disabled={isGenerating}
              fullWidth
              rows={2}
            />
          </EuiFormRow>
        </EuiFlexItem>
      </EuiFlexGroup>
      
      {/* Firecrawl Recommendation */}
      {firecrawlInfo && (
        <>
          <EuiSpacer size="m" />
          <FirecrawlBanner firecrawlInfo={firecrawlInfo} reason={firecrawlReason} />
        </>
      )}
      
      {/* Error Display (if not a Firecrawl situation) */}
      {error && !firecrawlInfo && (
        <>
          <EuiSpacer size="m" />
          <EuiCallOut title="Error" color="danger" iconType="error">
            {error}
          </EuiCallOut>
        </>
      )}
      
      {/* Progress Display */}
      {(isGenerating || currentPhase) && (
        <>
          <EuiSpacer size="l" />
          
          {/* Phase Progress */}
          <PhaseProgress 
            currentPhase={currentPhase} 
            iterationCount={iterationCount} 
          />
          
          {isGenerating && (
            <>
              <EuiSpacer size="s" />
              <EuiProgress size="xs" color="primary" />
            </>
          )}
          
          <EuiSpacer size="m" />
          
          {/* Event Log */}
          <EuiAccordion
            id="eventLog"
            buttonContent={
              <EuiText size="s">
                <strong>Activity Log</strong> ({events.length} events)
              </EuiText>
            }
            initialIsOpen={true}
          >
            <div 
              ref={eventLogRef}
              style={{ 
                maxHeight: 200, 
                overflowY: 'auto',
                padding: '8px 0',
              }}
            >
              {events.map((event, idx) => (
                <EventEntry 
                  key={idx} 
                  event={event} 
                  isLatest={idx === events.length - 1}
                />
              ))}
              {events.length === 0 && (
                <EuiText size="xs" color="subdued">
                  Waiting for events...
                </EuiText>
              )}
            </div>
          </EuiAccordion>
        </>
      )}
      
      {/* Investigation Summary */}
      {investigationSummary && (
        <>
          <EuiSpacer size="m" />
          <EuiAccordion
            id="investigationSummary"
            buttonContent={
              <EuiText size="s">
                <strong>Site Investigation Summary</strong>
              </EuiText>
            }
            initialIsOpen={false}
          >
            <EuiSpacer size="s" />
            <EuiPanel color="subdued" paddingSize="s">
              <EuiText size="xs">
                <ul>
                  <li><strong>Domain:</strong> {investigationSummary.domain}</li>
                  <li><strong>Pages Analyzed:</strong> {investigationSummary.page_fetch_summary?.successful || 0}</li>
                  {investigationSummary.robots_txt_status && (
                    <li><strong>robots.txt:</strong> {investigationSummary.robots_txt_status}</li>
                  )}
                  {investigationSummary.sitemaps && investigationSummary.sitemaps.length > 0 && (
                    <li><strong>Sitemaps Found:</strong> {investigationSummary.sitemaps.length}</li>
                  )}
                </ul>
              </EuiText>
            </EuiPanel>
          </EuiAccordion>
        </>
      )}
      
      {/* Sample Document Preview */}
      {sampleDocument && Object.keys(sampleDocument).length > 0 && (
        <>
          <EuiSpacer size="m" />
          <EuiAccordion
            id="sampleDocument"
            buttonContent={
              <EuiText size="s">
                <strong>Sample Extracted Document</strong>
              </EuiText>
            }
            initialIsOpen={true}
          >
            <EuiSpacer size="s" />
            <EuiPanel color="subdued" paddingSize="s">
              <EuiCode language="json" transparentBackground>
                {JSON.stringify(sampleDocument, null, 2)}
              </EuiCode>
            </EuiPanel>
          </EuiAccordion>
        </>
      )}
      
      {/* Completion Actions */}
      {currentPhase === 'complete' && yamlContent && (
        <>
          <EuiSpacer size="l" />
          <EuiCallOut 
            title="Configuration Generated Successfully" 
            color="success" 
            iconType="checkInCircleFilled"
          >
            <p>Your crawler configuration is ready. View the preview below or download the YAML file.</p>
          </EuiCallOut>
          
          <EuiSpacer size="m" />
          
          <EuiFlexGroup>
            <EuiFlexItem grow={false}>
              <EuiButton iconType="refresh" onClick={handleReset}>
                Start Over
              </EuiButton>
            </EuiFlexItem>
          </EuiFlexGroup>
        </>
      )}
    </EuiPanel>
  );
}
