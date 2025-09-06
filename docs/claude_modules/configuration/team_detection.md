# Dynamic Team Configuration

## Project Type Detection
The orchestrator automatically detects project types and deploys appropriate teams.

### Web Application Indicators
- `package.json`, `requirements.txt`, `Gemfile`
- Frontend frameworks (React, Vue, Angular)
- API/backend frameworks (Express, Django, Rails)

### System Deployment Indicators
- Deployment specs/plans (`*_deployment_*.md`)
- Infrastructure configs (Terraform, Ansible)
- Docker/Kubernetes manifests
- Systemd service files

### Data Pipeline Indicators
- ETL scripts, data processing code
- Database migration files
- Apache Airflow, Luigi, or similar
- Large data directories

### Infrastructure as Code Indicators
- Terraform files (`*.tf`)
- CloudFormation templates
- Ansible playbooks
- Pulumi code

## Team Templates

### Web Application
- **Core**: orchestrator, developer, tester, testrunner
- **Optional**: devops, researcher, documentation_writer

### System Deployment
- **Core**: orchestrator, sysadmin, devops, securityops
- **Optional**: networkops, monitoringops, databaseops

### Data Pipeline
- **Core**: orchestrator, developer, databaseops, devops
- **Optional**: monitoringops, researcher

### Infrastructure as Code
- **Core**: orchestrator, devops, sysadmin, securityops
- **Optional**: networkops, monitoringops

