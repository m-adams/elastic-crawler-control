"""
Agents package for the Elastic Crawler Service.

This package contains Agno-powered agents and workflows:
- site_investigation: Investigates websites to understand structure and content
- site_investigation_tools: Agno tools for site investigation
- config_generation: Generates Open Crawler YAML configurations
- config_generation_tools: Agno tools for config generation
- config_validation: Validates Open Crawler configurations
- config_validation_tools: Agno tools for config validation
- orchestration_workflow: Main workflow orchestrating all agents
- workflow_models: Pydantic models for workflow state and I/O

The agents use the Agno framework with the Elastic LLM Proxy for AI capabilities.
"""

from agents.site_investigation import (
    SiteInvestigationAgent,
    create_site_investigation_agent,
    SITE_INVESTIGATION_INSTRUCTIONS,
)
from agents.site_investigation_tools import (
    fetch_robots_txt,
    fetch_sitemap_urls,
    fetch_pages,
    analyze_page_structure,
    analyze_page_patterns,
    select_sample_urls,
    generate_recommendations,
    SITE_INVESTIGATION_TOOLS,
)
from agents.config_generation import (
    ConfigGenerationAgent,
    create_config_generation_agent,
    CONFIG_GENERATION_INSTRUCTIONS,
)
from agents.config_generation_tools import (
    load_knowledge_patterns,
    generate_domain_config,
    generate_crawl_rules,
    generate_extraction_rules,
    generate_full_config,
    validate_config_structure,
    CONFIG_GENERATION_TOOLS,
)
from agents.config_validation import (
    ConfigValidationAgent,
    create_config_validation_agent,
    CONFIG_VALIDATION_INSTRUCTIONS,
)
from agents.config_validation_tools import (
    validate_yaml_syntax,
    validate_schema,
    check_extraction_rules,
    check_crawl_rules,
    generate_validation_report,
    CONFIG_VALIDATION_TOOLS,
)
from agents.orchestration_workflow import (
    ConfigGenerationWorkflow,
    OrchestrationWorkflow,
    create_config_workflow,
)
from agents.workflow_models import (
    WorkflowInput,
    WorkflowState,
    WorkflowPhase,
    WorkflowResult,
    InvestigationResult,
    ConfigGenerationResult,
    ValidationResult,
    ConfirmationType,
    ConfirmationRequest,
    ConfirmationResponse,
)

__all__ = [
    # Site Investigation Agent
    "SiteInvestigationAgent",
    "create_site_investigation_agent",
    "SITE_INVESTIGATION_INSTRUCTIONS",
    # Site Investigation Tools
    "fetch_robots_txt",
    "fetch_sitemap_urls",
    "fetch_pages",
    "analyze_page_structure",
    "analyze_page_patterns",
    "select_sample_urls",
    "generate_recommendations",
    "SITE_INVESTIGATION_TOOLS",
    # Config Generation Agent
    "ConfigGenerationAgent",
    "create_config_generation_agent",
    "CONFIG_GENERATION_INSTRUCTIONS",
    # Config Generation Tools
    "load_knowledge_patterns",
    "generate_domain_config",
    "generate_crawl_rules",
    "generate_extraction_rules",
    "generate_full_config",
    "validate_config_structure",
    "CONFIG_GENERATION_TOOLS",
    # Config Validation Agent
    "ConfigValidationAgent",
    "create_config_validation_agent",
    "CONFIG_VALIDATION_INSTRUCTIONS",
    # Config Validation Tools
    "validate_yaml_syntax",
    "validate_schema",
    "check_extraction_rules",
    "check_crawl_rules",
    "generate_validation_report",
    "CONFIG_VALIDATION_TOOLS",
    # Orchestration Workflow
    "ConfigGenerationWorkflow",
    "OrchestrationWorkflow",
    "create_config_workflow",
    # Workflow Models
    "WorkflowInput",
    "WorkflowState",
    "WorkflowPhase",
    "WorkflowResult",
    "InvestigationResult",
    "ConfigGenerationResult",
    "ValidationResult",
    "ConfirmationType",
    "ConfirmationRequest",
    "ConfirmationResponse",
]
