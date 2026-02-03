"""
Extraction Testing API Endpoints.

Provides endpoints for testing extraction rules using Open Crawler's urltest command.
This allows users to validate that their extraction rules work correctly before running
a full crawl.

Endpoints:
- POST /api/extraction/validate - Validate config against real crawler
- POST /api/extraction/test - Test extraction on a single URL
- POST /api/extraction/batch - Test extraction on multiple URLs
- POST /api/extraction/evaluate - Evaluate extraction quality against expected fields

@see Beads issue 4nr - Extraction Rule Testing with urltest
@see Beads issue xj6 - Crawler Test API Endpoints
"""

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from utils.crawler_client import (
    CrawlerClient,
    UrlTestResult,
    ValidationResult,
    get_crawler_client,
)

router = APIRouter(prefix="/api/extraction", tags=["extraction"])


# =============================================================================
# Request/Response Models
# =============================================================================


class ValidateConfigRequest(BaseModel):
    """Request to validate a crawler config."""
    config: Optional[Dict[str, Any]] = Field(default=None, description="Open Crawler configuration dict")
    yaml_content: Optional[str] = Field(default=None, description="YAML content string (alternative to config dict)")


class ValidateConfigResponse(BaseModel):
    """Response from config validation."""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    raw_output: Optional[str] = None


class ExtractionTestRequest(BaseModel):
    """Request to test extraction on a single URL."""
    config: Dict[str, Any] = Field(..., description="Open Crawler configuration dict")
    url: str = Field(..., description="URL to test extraction on")


class ExtractionTestResponse(BaseModel):
    """Response from extraction test."""
    success: bool
    url: str
    extracted_document: Optional[Dict[str, Any]] = None
    extracted_fields: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    blocked: bool = False
    block_reason: Optional[str] = None
    raw_output: Optional[str] = None


class BatchExtractionRequest(BaseModel):
    """Request to test extraction on multiple URLs."""
    config: Dict[str, Any] = Field(..., description="Open Crawler configuration dict")
    urls: List[str] = Field(..., description="URLs to test extraction on")
    stop_on_error: bool = Field(default=False, description="Stop on first error")


class BatchExtractionResponse(BaseModel):
    """Response from batch extraction test."""
    total_urls: int
    successful: int
    failed: int
    blocked: int
    results: List[ExtractionTestResponse]
    extraction_rate: float = Field(description="Percentage of successful extractions")


class EvaluationRequest(BaseModel):
    """Request to evaluate extraction quality."""
    config: Dict[str, Any] = Field(..., description="Open Crawler configuration dict")
    urls: List[str] = Field(..., description="URLs to test")
    expected_fields: List[str] = Field(..., description="Fields expected to be extracted")
    required_fields: Optional[List[str]] = Field(default=None, description="Fields that MUST be present")


class FieldEvaluation(BaseModel):
    """Evaluation of a single field across all URLs."""
    field_name: str
    present_count: int
    total_urls: int
    extraction_rate: float
    sample_values: List[str] = Field(default_factory=list)
    is_required: bool = False
    status: str = Field(description="'pass', 'warning', or 'fail'")


class EvaluationResponse(BaseModel):
    """Response from extraction evaluation."""
    overall_status: str = Field(description="'pass', 'warning', or 'fail'")
    total_urls_tested: int
    successful_extractions: int
    field_evaluations: List[FieldEvaluation]
    recommendations: List[str] = Field(default_factory=list)
    sample_documents: List[Dict[str, Any]] = Field(default_factory=list)


# =============================================================================
# Helper Functions
# =============================================================================


def get_expected_fields_from_config(config: Dict[str, Any]) -> List[str]:
    """Extract expected field names from extraction rules in config."""
    fields = []
    domains = config.get("domains", [])
    for domain in domains:
        for ruleset in domain.get("extraction_rulesets", []):
            for rule in ruleset.get("rules", []):
                if rule.get("action") == "extract" and rule.get("field_name"):
                    fields.append(rule["field_name"])
    return fields


def urltest_to_response(result: UrlTestResult) -> ExtractionTestResponse:
    """Convert UrlTestResult to ExtractionTestResponse."""
    extracted_fields = []
    if result.extracted_document:
        extracted_fields = list(result.extracted_document.keys())
    
    return ExtractionTestResponse(
        success=result.success,
        url=result.url,
        extracted_document=result.extracted_document,
        extracted_fields=extracted_fields,
        missing_fields=[],  # Will be populated by caller if needed
        error=result.error,
        blocked=result.blocked,
        block_reason=result.block_reason,
        raw_output=result.raw_output[:500] if result.raw_output else None,
    )


# =============================================================================
# API Endpoints
# =============================================================================


@router.post("/test", response_model=ExtractionTestResponse)
async def test_extraction(request: ExtractionTestRequest) -> ExtractionTestResponse:
    """
    Test extraction on a single URL using Open Crawler's urltest command.
    
    This endpoint:
    1. Writes the config to a temp file
    2. Runs `bin/crawler urltest config.yml URL`
    3. Parses the extracted document from output
    4. Returns the extracted fields
    
    Args:
        request: ExtractionTestRequest with config and URL
        
    Returns:
        ExtractionTestResponse with extracted document and field analysis
        
    Raises:
        HTTPException: If crawler is not available
    """
    client = get_crawler_client()
    
    if not client.is_available():
        raise HTTPException(
            status_code=503,
            detail="Open Crawler is not available. Ensure crawler is installed at CRAWLER_PATH."
        )
    
    try:
        result = await client.urltest(request.config, request.url)
        response = urltest_to_response(result)
        
        # Calculate missing fields
        expected_fields = get_expected_fields_from_config(request.config)
        if result.extracted_document:
            response.missing_fields = [
                f for f in expected_fields 
                if f not in result.extracted_document
            ]
        else:
            response.missing_fields = expected_fields
        
        return response
        
    except TimeoutError as e:
        return ExtractionTestResponse(
            success=False,
            url=request.url,
            error=f"Timeout: {str(e)}",
        )
    except Exception as e:
        return ExtractionTestResponse(
            success=False,
            url=request.url,
            error=f"Error: {str(e)}",
        )


@router.post("/batch", response_model=BatchExtractionResponse)
async def test_extraction_batch(request: BatchExtractionRequest) -> BatchExtractionResponse:
    """
    Test extraction on multiple URLs.
    
    Runs urltest on each URL sequentially and aggregates results.
    Useful for validating extraction rules across different page types.
    
    Args:
        request: BatchExtractionRequest with config and list of URLs
        
    Returns:
        BatchExtractionResponse with aggregated results
    """
    client = get_crawler_client()
    
    if not client.is_available():
        raise HTTPException(
            status_code=503,
            detail="Open Crawler is not available."
        )
    
    results = []
    successful = 0
    failed = 0
    blocked = 0
    
    expected_fields = get_expected_fields_from_config(request.config)
    
    for url in request.urls:
        try:
            result = await client.urltest(request.config, url)
            response = urltest_to_response(result)
            
            # Calculate missing fields
            if result.extracted_document:
                response.missing_fields = [
                    f for f in expected_fields 
                    if f not in result.extracted_document
                ]
            else:
                response.missing_fields = expected_fields
            
            results.append(response)
            
            if result.success:
                successful += 1
            elif result.blocked:
                blocked += 1
            else:
                failed += 1
                
            # Stop on first error if requested
            if request.stop_on_error and not result.success:
                break
                
        except Exception as e:
            results.append(ExtractionTestResponse(
                success=False,
                url=url,
                error=str(e),
                missing_fields=expected_fields,
            ))
            failed += 1
            
            if request.stop_on_error:
                break
    
    total = len(results)
    extraction_rate = (successful / total * 100) if total > 0 else 0.0
    
    return BatchExtractionResponse(
        total_urls=total,
        successful=successful,
        failed=failed,
        blocked=blocked,
        results=results,
        extraction_rate=round(extraction_rate, 1),
    )


@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_extraction(request: EvaluationRequest) -> EvaluationResponse:
    """
    Evaluate extraction quality against expected fields.
    
    This endpoint:
    1. Tests extraction on all provided URLs
    2. Evaluates how well each expected field is extracted
    3. Provides recommendations for improving extraction
    
    Use this to determine if extraction rules need adjustment before running
    a full crawl.
    
    Args:
        request: EvaluationRequest with config, URLs, and expected fields
        
    Returns:
        EvaluationResponse with detailed field evaluations and recommendations
    """
    client = get_crawler_client()
    
    if not client.is_available():
        raise HTTPException(
            status_code=503,
            detail="Open Crawler is not available."
        )
    
    # Test all URLs
    results = await client.urltest_batch(
        request.config,
        request.urls,
        stop_on_error=False,
    )
    
    # Track field presence across all URLs
    field_presence: Dict[str, List[Any]] = {f: [] for f in request.expected_fields}
    sample_documents = []
    successful_extractions = 0
    
    for result in results:
        if result.success and result.extracted_document:
            successful_extractions += 1
            sample_documents.append(result.extracted_document)
            
            for field in request.expected_fields:
                value = result.extracted_document.get(field)
                if value:
                    field_presence[field].append(value)
    
    # Evaluate each field
    field_evaluations = []
    required_fields = set(request.required_fields or [])
    
    for field_name in request.expected_fields:
        values = field_presence[field_name]
        is_required = field_name in required_fields
        present_count = len(values)
        total_urls = len(results)
        extraction_rate = (present_count / total_urls * 100) if total_urls > 0 else 0.0
        
        # Determine status
        if extraction_rate >= 80:
            status = "pass"
        elif extraction_rate >= 50:
            status = "warning"
        else:
            status = "fail"
        
        # Required fields have stricter criteria
        if is_required and extraction_rate < 90:
            status = "fail"
        
        # Get sample values (truncate long strings)
        sample_values = []
        for v in values[:3]:
            v_str = str(v)[:100]
            if len(str(v)) > 100:
                v_str += "..."
            sample_values.append(v_str)
        
        field_evaluations.append(FieldEvaluation(
            field_name=field_name,
            present_count=present_count,
            total_urls=total_urls,
            extraction_rate=round(extraction_rate, 1),
            sample_values=sample_values,
            is_required=is_required,
            status=status,
        ))
    
    # Generate recommendations
    recommendations = []
    
    for eval in field_evaluations:
        if eval.status == "fail":
            recommendations.append(
                f"Field '{eval.field_name}' extraction rate is low ({eval.extraction_rate}%). "
                f"Review selector or add fallback selectors."
            )
        elif eval.status == "warning":
            recommendations.append(
                f"Field '{eval.field_name}' partially extracts ({eval.extraction_rate}%). "
                f"Consider adding more selector patterns."
            )
    
    if successful_extractions == 0:
        recommendations.insert(0, "No successful extractions. Check if site is blocking requests or selectors are incorrect.")
    
    blocked_count = sum(1 for r in results if r.blocked)
    if blocked_count > 0:
        recommendations.append(
            f"{blocked_count} URLs were blocked. Consider adjusting user agent or rate limiting."
        )
    
    # Determine overall status
    fail_count = sum(1 for e in field_evaluations if e.status == "fail")
    warning_count = sum(1 for e in field_evaluations if e.status == "warning")
    
    if fail_count > 0:
        overall_status = "fail"
    elif warning_count > 0:
        overall_status = "warning"
    else:
        overall_status = "pass"
    
    return EvaluationResponse(
        overall_status=overall_status,
        total_urls_tested=len(results),
        successful_extractions=successful_extractions,
        field_evaluations=field_evaluations,
        recommendations=recommendations,
        sample_documents=sample_documents[:3],  # Limit to 3 samples
    )


@router.get("/status")
async def extraction_status():
    """
    Check if extraction testing is available.
    
    Returns:
        Status information including crawler availability
    """
    client = get_crawler_client()
    
    return {
        "available": client.is_available(),
        "crawler_path": client.crawler_path,
        "message": "Ready for extraction testing" if client.is_available() else "Crawler not available",
    }


@router.post("/validate", response_model=ValidateConfigResponse)
async def validate_config(request: ValidateConfigRequest) -> ValidateConfigResponse:
    """
    Validate a config using Open Crawler's validate command.
    
    Runs: bin/crawler validate config.yml
    
    This catches issues that YAML schema validation alone would miss,
    such as invalid selectors, missing required fields, or config
    structure problems.
    
    Accepts either:
    - config: A parsed config dictionary
    - yaml_content: A YAML string to parse and validate
    
    Args:
        request: ValidateConfigRequest with config dict or yaml_content
        
    Returns:
        ValidateConfigResponse with validation results
        
    Raises:
        HTTPException: If crawler is not available or input is invalid
    """
    import yaml
    
    # Parse YAML content if provided
    config = request.config
    if request.yaml_content:
        try:
            config = yaml.safe_load(request.yaml_content)
            if not isinstance(config, dict):
                return ValidateConfigResponse(
                    valid=False,
                    errors=["YAML content must be a valid configuration object"],
                )
        except yaml.YAMLError as e:
            return ValidateConfigResponse(
                valid=False,
                errors=[f"Invalid YAML syntax: {str(e)}"],
            )
    
    if not config:
        return ValidateConfigResponse(
            valid=False,
            errors=["No config provided. Send either 'config' dict or 'yaml_content' string."],
        )
    
    client = get_crawler_client()
    
    # If crawler is not available, do basic schema validation only
    if not client.is_available():
        # Import validation tools for fallback
        from agents.config_validation_tools import validate_schema
        
        schema_result = validate_schema(config)
        return ValidateConfigResponse(
            valid=schema_result.get("valid", False),
            errors=schema_result.get("errors", []),
            warnings=schema_result.get("warnings", []) + [
                "Note: Crawler binary not available. Only schema validation performed."
            ],
            raw_output="Crawler not available - schema validation only",
        )
    
    try:
        result = await client.validate(config)
        
        return ValidateConfigResponse(
            valid=result.valid,
            errors=result.errors,
            warnings=result.warnings,
            raw_output=result.raw_output[:1000] if result.raw_output else None,
        )
        
    except TimeoutError as e:
        return ValidateConfigResponse(
            valid=False,
            errors=[f"Validation timed out: {str(e)}"],
        )
    except Exception as e:
        return ValidateConfigResponse(
            valid=False,
            errors=[f"Validation error: {str(e)}"],
        )
