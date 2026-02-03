/**
 * ExtractionTester Component
 * 
 * Tests extraction rules against real URLs using the /api/extraction endpoints.
 * Shows extracted fields, success rate, and recommendations.
 * 
 * @see Beads issue 4nr - Extraction Rule Testing with urltest
 */

import React, { useState, useCallback } from 'react';
import {
  EuiPanel,
  EuiFlexGroup,
  EuiFlexItem,
  EuiButton,
  EuiButtonEmpty,
  EuiFieldText,
  EuiText,
  EuiSpacer,
  EuiCallOut,
  EuiProgress,
  EuiCode,
  EuiIcon,
  EuiBadge,
  EuiTitle,
  EuiAccordion,
  EuiFormRow,
  EuiLoadingSpinner,
  EuiHealth,
  EuiToolTip,
  EuiModal,
  EuiModalHeader,
  EuiModalHeaderTitle,
  EuiModalBody,
  EuiModalFooter,
} from '@elastic/eui';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

/**
 * Field Evaluation Result Display
 */
function FieldEvaluationRow({ evaluation }) {
  const statusColors = {
    pass: 'success',
    warning: 'warning',
    fail: 'danger',
  };
  
  const statusIcons = {
    pass: 'checkInCircleFilled',
    warning: 'warning',
    fail: 'crossInACircleFilled',
  };
  
  return (
    <EuiFlexGroup 
      alignItems="center" 
      gutterSize="m"
      style={{ 
        padding: '8px 12px',
        borderBottom: '1px solid #EEF2F7',
      }}
    >
      <EuiFlexItem grow={false} style={{ width: 24 }}>
        <EuiIcon 
          type={statusIcons[evaluation.status]} 
          color={statusColors[evaluation.status]} 
        />
      </EuiFlexItem>
      
      <EuiFlexItem grow={2}>
        <EuiCode>{evaluation.field_name}</EuiCode>
        {evaluation.is_required && (
          <EuiBadge color="danger" style={{ marginLeft: 4 }}>Required</EuiBadge>
        )}
      </EuiFlexItem>
      
      <EuiFlexItem grow={1}>
        <EuiText size="xs">
          {evaluation.present_count} / {evaluation.total_urls} URLs
        </EuiText>
      </EuiFlexItem>
      
      <EuiFlexItem grow={1}>
        <EuiHealth color={statusColors[evaluation.status]}>
          {evaluation.extraction_rate}%
        </EuiHealth>
      </EuiFlexItem>
      
      <EuiFlexItem grow={3}>
        {evaluation.sample_values.length > 0 ? (
          <EuiToolTip content={evaluation.sample_values.join(', ')}>
            <EuiText size="xs" color="subdued" style={{ fontStyle: 'italic' }}>
              "{evaluation.sample_values[0].substring(0, 40)}
              {evaluation.sample_values[0].length > 40 ? '...' : ''}"
            </EuiText>
          </EuiToolTip>
        ) : (
          <EuiText size="xs" color="danger">No values extracted</EuiText>
        )}
      </EuiFlexItem>
    </EuiFlexGroup>
  );
}

/**
 * Single URL Test Result
 */
function UrlTestResult({ result, index }) {
  return (
    <EuiAccordion
      id={`url-result-${index}`}
      buttonContent={
        <EuiFlexGroup alignItems="center" gutterSize="s">
          <EuiFlexItem grow={false}>
            <EuiIcon 
              type={result.success ? 'checkInCircleFilled' : 'crossInACircleFilled'} 
              color={result.success ? 'success' : 'danger'} 
            />
          </EuiFlexItem>
          <EuiFlexItem>
            <EuiText size="s">
              {result.url}
              {result.blocked && (
                <EuiBadge color="warning" style={{ marginLeft: 8 }}>Blocked</EuiBadge>
              )}
            </EuiText>
          </EuiFlexItem>
          {result.extracted_fields && (
            <EuiFlexItem grow={false}>
              <EuiBadge color="hollow">
                {result.extracted_fields.length} fields
              </EuiBadge>
            </EuiFlexItem>
          )}
        </EuiFlexGroup>
      }
    >
      <EuiSpacer size="s" />
      <EuiPanel color="subdued" paddingSize="s">
        {result.error && (
          <EuiCallOut color="danger" iconType="alert" title="Error" size="s">
            {result.error}
          </EuiCallOut>
        )}
        
        {result.blocked && result.block_reason && (
          <EuiCallOut color="warning" iconType="alert" title="Blocked" size="s">
            {result.block_reason}
          </EuiCallOut>
        )}
        
        {result.extracted_document && (
          <>
            <EuiText size="xs"><strong>Extracted Document:</strong></EuiText>
            <EuiSpacer size="xs" />
            <div style={{ 
              fontFamily: 'monospace', 
              fontSize: '11px',
              backgroundColor: '#1D1E24',
              color: '#DFE5EF',
              padding: '8px',
              borderRadius: '4px',
              maxHeight: '200px',
              overflow: 'auto',
            }}>
              <pre style={{ margin: 0 }}>
                {JSON.stringify(result.extracted_document, null, 2)}
              </pre>
            </div>
          </>
        )}
        
        {result.missing_fields && result.missing_fields.length > 0 && (
          <>
            <EuiSpacer size="s" />
            <EuiText size="xs" color="warning">
              <strong>Missing fields:</strong> {result.missing_fields.join(', ')}
            </EuiText>
          </>
        )}
      </EuiPanel>
    </EuiAccordion>
  );
}

/**
 * Main ExtractionTester Component
 */
export default function ExtractionTester({ 
  config, 
  isOpen, 
  onClose,
  onResultsReady,
}) {
  // Test URL input
  const [testUrls, setTestUrls] = useState('');
  
  // Testing state
  const [isTesting, setIsTesting] = useState(false);
  const [testProgress, setTestProgress] = useState(0);
  
  // Results
  const [evaluationResult, setEvaluationResult] = useState(null);
  const [error, setError] = useState(null);
  
  /**
   * Get expected fields from config
   */
  const getExpectedFields = useCallback(() => {
    const fields = [];
    if (config?.domains?.[0]?.extraction_rulesets) {
      for (const ruleset of config.domains[0].extraction_rulesets) {
        for (const rule of ruleset.rules || []) {
          if (rule.field_name) {
            fields.push(rule.field_name);
          }
        }
      }
    }
    return fields;
  }, [config]);
  
  /**
   * Run extraction evaluation
   */
  const handleRunTest = useCallback(async () => {
    if (!config || !testUrls.trim()) {
      setError('Please enter at least one URL to test');
      return;
    }
    
    setIsTesting(true);
    setError(null);
    setEvaluationResult(null);
    setTestProgress(0);
    
    // Parse URLs (one per line, or comma-separated)
    const urls = testUrls
      .split(/[\n,]/)
      .map(u => u.trim())
      .filter(u => u.length > 0 && u.startsWith('http'));
    
    if (urls.length === 0) {
      setError('No valid URLs found. URLs must start with http:// or https://');
      setIsTesting(false);
      return;
    }
    
    const expectedFields = getExpectedFields();
    
    try {
      setTestProgress(10);
      
      const response = await fetch(`${API_BASE}/extraction/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          config: config,
          urls: urls,
          expected_fields: expectedFields,
        }),
      });
      
      setTestProgress(80);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }
      
      const result = await response.json();
      setEvaluationResult(result);
      setTestProgress(100);
      
      // Notify parent of results
      if (onResultsReady && result.sample_documents?.[0]) {
        onResultsReady(result.sample_documents[0]);
      }
      
    } catch (err) {
      setError(err.message);
    } finally {
      setIsTesting(false);
    }
  }, [config, testUrls, getExpectedFields, onResultsReady]);
  
  /**
   * Get seed URLs from config as default test URLs
   */
  const handleUseSeedUrls = useCallback(() => {
    if (config?.domains?.[0]?.seed_urls) {
      setTestUrls(config.domains[0].seed_urls.join('\n'));
    }
  }, [config]);
  
  if (!isOpen) return null;
  
  const expectedFields = getExpectedFields();
  
  return (
    <EuiModal onClose={onClose} maxWidth="900px">
      <EuiModalHeader>
        <EuiModalHeaderTitle>
          <EuiFlexGroup alignItems="center" gutterSize="s">
            <EuiFlexItem grow={false}>
              <EuiIcon type="inspect" size="l" />
            </EuiFlexItem>
            <EuiFlexItem>
              Test Extraction Rules
            </EuiFlexItem>
          </EuiFlexGroup>
        </EuiModalHeaderTitle>
      </EuiModalHeader>
      
      <EuiModalBody>
        {/* Instructions */}
        <EuiCallOut 
          title="Test your extraction rules against real pages" 
          iconType="iInCircle"
          size="s"
        >
          <p>
            Enter URLs from the target site to verify that extraction rules work correctly.
            The crawler will fetch each page and attempt to extract the configured fields.
          </p>
        </EuiCallOut>
        
        <EuiSpacer size="m" />
        
        {/* URL Input */}
        <EuiFormRow 
          label="Test URLs" 
          helpText="Enter one URL per line"
          fullWidth
        >
          <div>
            <EuiFieldText
              value={testUrls}
              onChange={(e) => setTestUrls(e.target.value)}
              placeholder="https://example.com/article/1&#10;https://example.com/article/2"
              fullWidth
              disabled={isTesting}
              style={{ 
                fontFamily: 'monospace',
                minHeight: '80px',
              }}
              // Use textarea behavior
              as="textarea"
            />
            <EuiSpacer size="xs" />
            <EuiButtonEmpty 
              size="xs" 
              onClick={handleUseSeedUrls}
              disabled={isTesting || !config?.domains?.[0]?.seed_urls}
            >
              Use seed URLs from config
            </EuiButtonEmpty>
          </div>
        </EuiFormRow>
        
        <EuiSpacer size="m" />
        
        {/* Expected Fields */}
        <EuiText size="xs">
          <strong>Expected fields to extract ({expectedFields.length}):</strong>
        </EuiText>
        <EuiSpacer size="xs" />
        <EuiFlexGroup wrap responsive={false} gutterSize="xs">
          {expectedFields.map((field) => (
            <EuiFlexItem grow={false} key={field}>
              <EuiBadge color="hollow">{field}</EuiBadge>
            </EuiFlexItem>
          ))}
        </EuiFlexGroup>
        
        <EuiSpacer size="m" />
        
        {/* Run Test Button */}
        <EuiButton
          onClick={handleRunTest}
          fill
          isLoading={isTesting}
          iconType="play"
          disabled={!testUrls.trim() || !config}
        >
          {isTesting ? 'Testing...' : 'Run Extraction Test'}
        </EuiButton>
        
        {/* Progress */}
        {isTesting && (
          <>
            <EuiSpacer size="m" />
            <EuiProgress value={testProgress} max={100} size="s" />
            <EuiText size="xs" color="subdued">
              Testing extraction on {testUrls.split(/[\n,]/).filter(u => u.trim()).length} URLs...
            </EuiText>
          </>
        )}
        
        {/* Error */}
        {error && (
          <>
            <EuiSpacer size="m" />
            <EuiCallOut title="Error" color="danger" iconType="alert">
              {error}
            </EuiCallOut>
          </>
        )}
        
        {/* Results */}
        {evaluationResult && (
          <>
            <EuiSpacer size="l" />
            
            {/* Overall Status */}
            <EuiCallOut
              title={`Extraction Test ${evaluationResult.overall_status === 'pass' ? 'Passed' : evaluationResult.overall_status === 'warning' ? 'Passed with Warnings' : 'Failed'}`}
              color={evaluationResult.overall_status === 'pass' ? 'success' : evaluationResult.overall_status === 'warning' ? 'warning' : 'danger'}
              iconType={evaluationResult.overall_status === 'pass' ? 'checkInCircleFilled' : 'warning'}
            >
              <p>
                {evaluationResult.successful_extractions} of {evaluationResult.total_urls_tested} URLs extracted successfully.
              </p>
            </EuiCallOut>
            
            <EuiSpacer size="m" />
            
            {/* Field Evaluations */}
            <EuiTitle size="xs">
              <h4>Field Extraction Results</h4>
            </EuiTitle>
            <EuiSpacer size="s" />
            
            <EuiPanel paddingSize="none" style={{ border: '1px solid #D3DAE6' }}>
              {/* Header */}
              <EuiFlexGroup 
                alignItems="center" 
                gutterSize="m"
                style={{ 
                  padding: '8px 12px',
                  backgroundColor: '#F5F7FA',
                  borderBottom: '1px solid #D3DAE6',
                }}
              >
                <EuiFlexItem grow={false} style={{ width: 24 }} />
                <EuiFlexItem grow={2}>
                  <EuiText size="xs"><strong>Field</strong></EuiText>
                </EuiFlexItem>
                <EuiFlexItem grow={1}>
                  <EuiText size="xs"><strong>Coverage</strong></EuiText>
                </EuiFlexItem>
                <EuiFlexItem grow={1}>
                  <EuiText size="xs"><strong>Rate</strong></EuiText>
                </EuiFlexItem>
                <EuiFlexItem grow={3}>
                  <EuiText size="xs"><strong>Sample Value</strong></EuiText>
                </EuiFlexItem>
              </EuiFlexGroup>
              
              {/* Field rows */}
              {evaluationResult.field_evaluations.map((evaluation, idx) => (
                <FieldEvaluationRow key={idx} evaluation={evaluation} />
              ))}
            </EuiPanel>
            
            {/* Recommendations */}
            {evaluationResult.recommendations && evaluationResult.recommendations.length > 0 && (
              <>
                <EuiSpacer size="m" />
                <EuiTitle size="xs">
                  <h4>Recommendations</h4>
                </EuiTitle>
                <EuiSpacer size="s" />
                {evaluationResult.recommendations.map((rec, idx) => (
                  <EuiCallOut 
                    key={idx} 
                    color="warning" 
                    iconType="iInCircle" 
                    size="s"
                    style={{ marginBottom: 8 }}
                  >
                    {rec}
                  </EuiCallOut>
                ))}
              </>
            )}
            
            {/* Sample Documents */}
            {evaluationResult.sample_documents && evaluationResult.sample_documents.length > 0 && (
              <>
                <EuiSpacer size="m" />
                <EuiAccordion
                  id="sample-docs"
                  buttonContent={
                    <EuiText size="s">
                      <strong>Sample Extracted Documents ({evaluationResult.sample_documents.length})</strong>
                    </EuiText>
                  }
                >
                  <EuiSpacer size="s" />
                  {evaluationResult.sample_documents.map((doc, idx) => (
                    <div key={idx} style={{ marginBottom: 8 }}>
                      <div style={{ 
                        fontFamily: 'monospace', 
                        fontSize: '11px',
                        backgroundColor: '#1D1E24',
                        color: '#DFE5EF',
                        padding: '12px',
                        borderRadius: '4px',
                        maxHeight: '200px',
                        overflow: 'auto',
                      }}>
                        <pre style={{ margin: 0 }}>
                          {JSON.stringify(doc, null, 2)}
                        </pre>
                      </div>
                    </div>
                  ))}
                </EuiAccordion>
              </>
            )}
          </>
        )}
      </EuiModalBody>
      
      <EuiModalFooter>
        <EuiButtonEmpty onClick={onClose}>Close</EuiButtonEmpty>
      </EuiModalFooter>
    </EuiModal>
  );
}
