# Datasource Migration Plan

## Executive Summary

This document outlines a plan to restructure how Lorelai handles external data sources (currently
Slack and Google Drive). The goal is to create a more maintainable, extensible, and reliable system
for managing data sources, making it easier to add new ones in the future while improving the
stability of existing ones.

### Strategic Vision

The core principle behind this migration is the complete separation of concerns between Lorelai's
core functionality and its datasources. By treating datasources as independent, pluggable
components:

1. **Independent Development**:

   - Lorelai core can evolve without impacting existing datasources
   - Datasources can be developed and updated without requiring changes to Lorelai
   - Each datasource can have its own release cycle and versioning

1. **Third-Party Development**:

   - External developers can create new datasources without needing to understand Lorelai internals
   - Organizations can develop private datasources for internal systems
   - Community-driven ecosystem of datasources (ie. a Marketplace) becomes possible

1. **Operational Benefits**:

   - Datasources can be deployed and scaled independently
   - Issues in one datasource don't affect others
   - Easier to maintain and debug
   - Simplified testing and validation

This approach transforms Lorelai from a monolithic application into a platform where datasources are
first-class, pluggable components with clear boundaries and interfaces.

### Why This Matters

1. **Current Challenges**:

   - Data source code is tightly coupled with the core application
   - Adding new data sources requires changes across multiple parts of the codebase
   - Feature flags and configurations are scattered
   - Testing and maintaining data sources is complex
   - No standardized way to handle authentication and authorization

1. **Benefits of This Approach**:

   - Cleaner separation of concerns
   - Easier to add new data sources
   - Improved reliability through standardized interfaces
   - Better testing and maintenance
   - Simplified configuration management
   - Clear path for third-party data source development

1. **Impact on Development**:

   - Reduced development time for new data sources
   - Easier to maintain existing data sources
   - Better isolation for testing
   - Clearer ownership of code
   - Improved deployment flexibility

### Key Concepts

1. **Datasource Registry**:

   - Central system for managing all data sources
   - Handles discovery, loading, and lifecycle management
   - Provides consistent interface for all data sources

1. **Feature Management**:

   - Granular control over data source features
   - Centralized configuration
   - Runtime enabling/disabling of features

1. **Standardized Interfaces**:

   - Common patterns for authentication
   - Unified approach to data retrieval
   - Consistent error handling
   - Standard monitoring interfaces

### Risk Assessment

1. **Technical Risks**:

   - Data migration complexity
   - Potential for service disruption
   - Backward compatibility challenges

1. **Mitigation Strategies**:

   - Phased implementation approach
   - Comprehensive testing at each phase
   - Gradual migration of existing data
   - Maintaining backward compatibility

## Current State Analysis

### Datasource Points

#### Google Drive Datasource

1. Core Components:

   - `lorelai/indexers/googledriveindexer.py`: Main indexing logic
   - `lorelai/context_retrievers/googledrivecontextretriever.py`: Context retrieval
   - `app/helpers/googledrive.py`: Helper functions
   - `app/models/google_drive.py`: Data models
   - Dependencies: `langchain-googledrive==0.3.35`

1. Configuration:

   - Feature flag: `FEATURE_GOOGLE_DRIVE`
   - OAuth credentials and token management
   - Environment variables in `.env` and `.env.example`

#### Slack Datasource

1. Core Components:

   - `lorelai/indexers/slackindexer.py`: Main indexing logic
   - `lorelai/context_retrievers/slackcontextretriever.py`: Context retrieval
   - `app/helpers/slack.py`: Helper functions
   - Database tables for Slack data

1. Configuration:

   - Feature flag: `FEATURE_SLACK`
   - OAuth settings: `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, etc.
   - Scopes configuration

### Shared Patterns

1. Both datasources follow similar patterns:

   - Indexer implementation
   - Context retriever implementation
   - Authentication flow
   - Feature flag management
   - OAuth-based authentication

1. Common Code:

   - Base classes in `lorelai/indexer.py` and context retriever base classes
   - Authentication handling in `app/routes/authentication.py`
   - Datasource management in `app/helpers/datasources.py`

## Migration Plan

### Phase 1: Core Framework Development (Version 1.0.0)

Goal: Create a core framework that allows datasources to be discovered, loaded, and managed.

Out of scope:

- No actual datasources are implemented in this phase. Maybe a hello world datasource for testing
- No fancy installation or deployment automation

1. **Essential Interfaces**:

   - Implement the base datasource interface to standardize how datasources handle indexing and
     retrieval operations.

1. **Registry System**:

   - Build a simple discovery mechanism that allows the system to find and load datasources at
     runtime.

1. **Base Schema**:

   - Create registry tables to track all installed datasources and their versions.
   - Implement authentication state tables to manage OAuth tokens and refresh cycles.
   - Set up feature flag tables to store configuration for enabled/disabled features.

1. **Virtual Environment Management**:

   - Implement basic virtual environment creation to isolate each datasource's dependencies.
   - Add support for requirements.txt to manage datasource-specific package versions.
   - Create simple dependency validation to prevent version conflicts between datasources.

### Phase 2: Reference Implementation - GitHub (Version 1.1.0)

1. **Create GitHub Datasource**:

   - Implement core interfaces

   - Support key GitHub features:

     ```yaml
     # Example github/datasource.yaml
     name: "github"
     version: "1.0.0"
     author: "Helixiora Team"
     description: "GitHub datasource for repositories, issues, and pull requests"

     framework_version: ">=1.0.0,<2.0.0"

     features:
       repository_indexing:
         enabled: true
         config:
           content_types:
             - "markdown"
             - "code"
             - "issues"
             - "pull_requests"
           max_file_size_mb: 10
           include_private: false

       issue_tracking:
         enabled: true
         config:
           include_comments: true
           include_closed: true
           max_age_days: 365

       pull_requests:
         enabled: true
         config:
           include_reviews: true
           include_closed: true
           max_age_days: 180

     auth:
       type: "oauth2"
       required_scopes:
         - "repo"  # For private repo access (optional)
         - "read:org"  # For org repos (optional)

     env_vars:
       - name: "GITHUB_CLIENT_ID"
         description: "OAuth client ID for GitHub API"
       - name: "GITHUB_CLIENT_SECRET"
         description: "OAuth client secret for GitHub API"

     database:
       tables:
         - name: "github_repositories"
           description: "Tracked GitHub repositories"
         - name: "github_issues"
           description: "Repository issues and comments"
         - name: "github_pull_requests"
           description: "Pull requests and reviews"

     monitoring:
       health_check_endpoint: "/health"
       metrics:
         - name: "repositories_indexed"
           type: "counter"
         - name: "api_rate_limit_remaining"
           type: "gauge"
         - name: "indexing_errors"
           type: "counter"
     ```

1. **Core Functionality**:

   ```python
   # github/datasource.py
   from typing import List, Dict, Any
   from lorelai.datasources.interfaces.base import DatasourceBase
   from github import Github

   class GitHubDatasource(DatasourceBase):
       def __init__(self, config: Dict[str, Any]):
           self.client = Github(config.get('access_token'))
           self.rate_limit_handler = RateLimitHandler()

       async def index_repository(self, repo_name: str) -> None:
           """Index a GitHub repository and its contents."""
           repo = self.client.get_repo(repo_name)

           # Index repository metadata
           await self.index_metadata(repo)

           # Index issues if enabled
           if self.features['issue_tracking'].enabled:
               await self.index_issues(repo)

           # Index pull requests if enabled
           if self.features['pull_requests'].enabled:
               await self.index_pull_requests(repo)

      async def get_context(self, query: str) -> List[Dict[str, Any]]:
          """Retrieve context from indexed GitHub content based on the query."""
          # Implement actual retrieval logic here
          return []
   ```

1. **Database Schema**:

   ```sql
   -- GitHub specific tables
   CREATE TABLE github_repositories (
       id SERIAL PRIMARY KEY,
       github_id INTEGER NOT NULL,
       name TEXT NOT NULL,
       owner TEXT NOT NULL,
       description TEXT,
       default_branch TEXT,
       is_private BOOLEAN,
       last_indexed TIMESTAMP,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );

   CREATE TABLE github_issues (
       id SERIAL PRIMARY KEY,
       repository_id INTEGER REFERENCES github_repositories(id),
       issue_number INTEGER NOT NULL,
       title TEXT NOT NULL,
       body TEXT,
       state TEXT,
       author TEXT,
       labels JSONB,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );

   CREATE TABLE github_pull_requests (
       id SERIAL PRIMARY KEY,
       repository_id INTEGER REFERENCES github_repositories(id),
       pr_number INTEGER NOT NULL,
       title TEXT NOT NULL,
       body TEXT,
       state TEXT,
       author TEXT,
       base_branch TEXT,
       head_branch TEXT,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   ```

This reference implementation will serve as a template for future datasources, demonstrating:

- Clean interface implementation
- Content extraction patterns
- Error handling
- Testing approaches
- Documentation standards

### Phase 3: Google Drive and Slack Datasources (Version 1.2.0)

1. **Migrate Google Drive and Slack Datasources**:
   - Implement core interfaces
   - Support key Google Drive and Slack features:

### Phase 4: Platform Services (Version 1.3.0)

1. **Management UI**:

   - Datasource admin interface
   - Configuration management
   - Status monitoring
   - Feature flag control

1. **Monitoring System**:

   - Health checks
   - Metrics collection
   - Error tracking
   - Performance monitoring

1. **Security Framework**:

   - Authentication flows
   - Authorization system
   - Credential management
   - Security validation

### Phase 5: Additional Datasources (Version 2.0.0)

1. **Confluence**:

   - Content-focused datasource
   - Rich text handling
   - Permission management

1. **OneDrive**:

   - File storage system
   - Binary content handling
   - Folder structure

1. **Google Drive Migration**:

   - Apply learnings from GitHub and OneDrive
   - Migrate existing functionality
   - Enhance with new patterns

1. **Slack Migration**:

   - Apply learnings from all previous datasources
   - Real-time updates
   - Complex permission model

## technical implementation notes

1. Create Base Directory Structure:

   ```text
   # Core datasource framework
   lorelai/
   ├── datasources/
   │   ├── __init__.py
   │   ├── registry.py        # Datasource registry and loading mechanism
   │   ├── exceptions.py      # Framework-specific exceptions
   │   ├── interfaces/        # Core interfaces that datasources must implement
   │   │   ├── __init__.py
   │   │   └── base.py
   │   ├── config/           # Framework configuration
   │   │   ├── __init__.py
   │   │   └── feature_flags.py
   │   └── tests/
   │       ├── __init__.py
   │       ├── test_registry.py
   │       └── test_interfaces.py

   # Actual datasource implementations
   datasources/
   ├── README.md             # Documentation for creating new datasources
   ├── google_drive/        # Google Drive datasource
   │   ├── __init__.py
   │   ├── datasource.yaml  # Datasource manifest file
   │   ├── requirements.txt # Datasource-specific dependencies
   │   ├── datasource.py    # Main datasource class
   │   ├── indexer.py       # Indexing implementation
   │   ├── retriever.py     # Retrieval implementation
   │   ├── models.py        # Data models
   │   └── tests/
   └── slack/               # Slack datasource
       ├── __init__.py
       ├── datasource.yaml  # Datasource manifest file
       ├── requirements.txt # Datasource-specific dependencies
       ├── datasource.py    # Main datasource class
       ├── indexer.py       # Indexing implementation
       ├── retriever.py     # Retrieval implementation
       ├── models.py        # Data models
       └── tests/
   ```

1a. Datasource Manifest File: Each datasource must include a `datasource.yaml` file in its root
directory that defines its metadata and capabilities, eg:

```yaml
# Example datasource.yaml
name: "google_drive"
version: "1.0.0"
author: "Helixiora Team"
description: "Google Drive datasource for document indexing and retrieval"

# Minimum version of the datasource framework required
framework_version: ">=1.0.0"

# Features provided by this datasource
features:
  document_indexing:
    enabled: true
    config:
      supported_mime_types:
        - "application/pdf"
        - "text/plain"
        - "application/vnd.google-apps.document"
      max_file_size_mb: 50

  folder_sync:
    enabled: true
    config:
      watch_changes: true
      sync_interval_minutes: 30

# Authentication configuration
auth:
  type: "oauth2"
  required_scopes:
    - "https://www.googleapis.com/auth/drive.readonly"
    - "https://www.googleapis.com/auth/drive.metadata.readonly"

# Required environment variables
env_vars:
  - name: "GOOGLE_CLIENT_ID"
    description: "OAuth client ID for Google Drive API"
  - name: "GOOGLE_CLIENT_SECRET"
    description: "OAuth client secret for Google Drive API"

# Database tables required by this datasource
database:
  tables:
    - name: "google_drive_items"
      description: "Stores indexed Google Drive files"
    - name: "google_drive_folders"
      description: "Stores watched folder information"

# Monitoring and health check configuration
monitoring:
  health_check_endpoint: "/health"
  metrics:
    - name: "files_indexed"
      type: "counter"
      description: "Number of files indexed"
    - name: "indexing_errors"
      type: "counter"
      description: "Number of indexing errors"
```

1b. Dependency Management:

Each datasource needs to carefully manage its dependencies to ensure compatibility with both Lorelai
and other datasources. This is handled through several mechanisms:

1. **Version Constraints**:

   ```yaml
   # datasource.yaml
   name: "google_drive"
   version: "1.0.0"
   framework_version: ">=1.0.0,<2.0.0"  # Semantic versioning for framework compatibility

   # Python version requirements
   python_version: ">=3.8,<4.0"

   # Core dependencies that must be compatible
   core_dependencies:
     langchain: ">=0.3.0,<0.4.0"
     pydantic: ">=2.0.0,<3.0.0"
     sqlalchemy: ">=1.4.0,<2.0.0"
   ```

1. **Dependency Resolution**:

   ```python
   class DependencyResolver:
       def __init__(self):
           self.installed_datasources = {}

       def check_compatibility(self, manifest: Dict[str, Any]) -> bool:
           """Check if datasource dependencies are compatible with installed versions"""
           core_deps = manifest.get("core_dependencies", {})
           for dep, version_spec in core_deps.items():
               if not self._is_compatible(dep, version_spec):
                   return False
           return True

       def _is_compatible(self, package: str, version_spec: str) -> bool:
           """Check if required version is compatible with installed version"""
           installed_version = pkg_resources.get_distribution(package).version
           return pkg_resources.Requirement.parse(f"{package}{version_spec}").contains(installed_version)
   ```

1. **Conflict Resolution**:

   - Registry maintains a dependency graph
   - Detects potential conflicts before loading datasources
   - Provides clear error messages for incompatible dependencies

   ```python
   class DependencyGraph:
       def __init__(self):
           self.graph = networkx.DiGraph()

       def add_datasource(self, manifest: Dict[str, Any]):
           """Add datasource and its dependencies to the graph"""
           name = manifest["name"]
           self.graph.add_node(name)
           for dep, version in manifest.get("core_dependencies", {}).items():
               self.graph.add_edge(name, dep, version=version)

       def check_conflicts(self) -> List[str]:
           """Return list of dependency conflicts"""
           conflicts = []
           for node in self.graph.nodes:
               versions = self._get_required_versions(node)
               for dep, reqs in versions.items():
                   if not self._versions_compatible(reqs):
                       conflicts.append(f"Conflict in {dep}: {reqs}")
           return conflicts
   ```

1. **Version Management**:

   - Semantic versioning for datasources and framework
   - Clear upgrade paths and compatibility matrices
   - Automated compatibility testing

   ```python
   class VersionManager:
       def check_framework_compatibility(self, required_version: str) -> bool:
           """Check if datasource is compatible with current framework version"""
           current_version = self.get_framework_version()
           return pkg_resources.Requirement.parse(f"framework{required_version}").contains(current_version)

       def get_upgrade_path(self, current_version: str, target_version: str) -> List[str]:
           """Determine steps needed to upgrade from current to target version"""
           # Implementation for determining upgrade steps
   ```

This system ensures that:

- Each datasource can specify exact dependency requirements
- Dependencies are properly isolated
- Conflicts are detected early
- Clear upgrade paths are available
- Framework compatibility is maintained

1. Define Core Interfaces:

   ```python
   # lorelai/datasources/interfaces/base.py
   from abc import ABC, abstractmethod
   from typing import Dict, Any, Optional

   class DatasourceBase(ABC):
       @abstractmethod
       def get_name(self) -> str:
           """Return the unique name of the datasource."""
           pass

       @abstractmethod
       def get_features(self) -> Dict[str, bool]:
           """Return a dictionary of available features and their status."""
           pass

       @abstractmethod
       def get_config(self) -> Dict[str, Any]:
           """Return the datasource configuration."""
           pass

       @abstractmethod
       def validate_config(self) -> bool:
           """Validate the datasource configuration."""
           pass
   ```

1. Create Feature Flag System:

   ```python
   # config/feature_flags.py
   from dataclasses import dataclass
   from typing import Dict, List

   @dataclass
   class DatasourceFeature:
       name: str
       enabled: bool
       dependencies: List[str] = None
       config: Dict[str, Any] = None

   class DatasourceFeatureFlags:
       def __init__(self):
           self.features: Dict[str, DatasourceFeature] = {}

       def register_feature(self, datasource: str, feature: str, enabled: bool = False):
           key = f"{datasource}.{feature}"
           self.features[key] = DatasourceFeature(name=key, enabled=enabled)
   ```

1. Implement Registry:

   ```python
   # registry.py
   from typing import Dict, Type, Optional
   from .interfaces.base import DatasourceBase
   from .config.feature_flags import DatasourceFeatureFlags

   class DatasourceRegistry:
       _instance = None
       _datasources: Dict[str, Type[DatasourceBase]] = {}
       _feature_flags = DatasourceFeatureFlags()

       @classmethod
       def get_instance(cls):
           if cls._instance is None:
               cls._instance = cls()
           return cls._instance

       def register_datasource(self, datasource_class: Type[DatasourceBase]):
           name = datasource_class.get_name()
           self._datasources[name] = datasource_class
   ```

1. Database Schema:

   ```sql
   -- Base tables for datasource management
   CREATE TABLE datasource_registry (
       id SERIAL PRIMARY KEY,
       name VARCHAR(50) NOT NULL UNIQUE,
       version VARCHAR(20),
       enabled BOOLEAN DEFAULT true,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );

   CREATE TABLE datasource_feature_flags (
       id SERIAL PRIMARY KEY,
       datasource_id INTEGER REFERENCES datasource_registry(id),
       feature_name VARCHAR(50) NOT NULL,
       enabled BOOLEAN DEFAULT false,
       config JSONB,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       UNIQUE(datasource_id, feature_name)
   );
   ```

1. SQLAlchemy Models:

   ```python
   # models/datasource.py
   from datetime import datetime
   from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
   from sqlalchemy.orm import relationship

   class DatasourceRegistry(db.Model):
       __tablename__ = 'datasource_registry'

       id = Column(Integer, primary_key=True)
       name = Column(String(50), unique=True, nullable=False)
       version = Column(String(20))
       enabled = Column(Boolean, default=True)
       created_at = Column(DateTime, default=datetime.utcnow)
       updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

   class DatasourceFeatureFlag(db.Model):
       __tablename__ = 'datasource_feature_flags'

       id = Column(Integer, primary_key=True)
       datasource_id = Column(Integer, ForeignKey('datasource_registry.id'))
       feature_name = Column(String(50), nullable=False)
       enabled = Column(Boolean, default=False)
       config = Column(JSON)
       created_at = Column(DateTime, default=datetime.utcnow)
       updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
   ```

1. Basic Admin UI Components:

   ```javascript
   // static/js/datasource-admin.js
   class DatasourceAdmin {
       constructor() {
           this.featureFlags = {};
       }

       async loadDatasources() {
           const response = await fetch('/api/v1/datasources');
           this.datasources = await response.json();
           this.renderDatasources();
       }

       async toggleFeature(datasource, feature) {
           await fetch(`/api/v1/datasources/${datasource}/features/${feature}`, {
               method: 'POST',
               headers: {
                   'Content-Type': 'application/json',
               },
               body: JSON.stringify({
                   enabled: !this.featureFlags[`${datasource}.${feature}`]
               })
           });
       }
   }
   ```

1. API Endpoints:

   ```python
   # routes/api/v1/datasources.py
   @datasource_bp.route('/api/v1/datasources', methods=['GET'])
   def list_datasources():
       registry = DatasourceRegistry.get_instance()
       return jsonify(registry.get_all_datasources())

   @datasource_bp.route('/api/v1/datasources/<datasource>/features/<feature>', methods=['POST'])
   def toggle_feature(datasource, feature):
       registry = DatasourceRegistry.get_instance()
       return jsonify(registry.toggle_feature(datasource, feature))
   ```

## Next Steps

1. Review and approve the plan
1. Set up project timeline
1. Create detailed technical specifications for each phase
1. Set up development environments
1. Begin Phase 1 implementation

Please review this plan and provide feedback on the questions and approach. We can adjust the phases
and timeline based on your requirements.
