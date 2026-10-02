# ADR-008: Use Controlled Production Deployment with Approval

## Status

Accepted

## Context

Terraform changes can modify Azure infrastructure, so applying every successful CI plan automatically could cause infrastructure changes without an explicit release decision.

The project therefore needs to demonstrate the distinction between continuous validation and controlled infrastructure deployment.

## Decision

Require an explicit production approval before Terraform Apply.

The CD pipeline first creates and publishes a Terraform plan artifact.

After approval, the pipeline downloads and applies the saved plan rather than creating a new plan during the Apply stage.

The deployment then performs post-deployment smoke validation.

## Deployment Flow

```text
CD Plan
   |
   v
Terraform Plan
   |
   v
Publish tfplan Artifact
   |
   v
Production Approval
   |
   v
Download Saved Plan
   |
   v
Terraform Apply
   |
   v
Smoke Validation
```

## Alternatives Considered

### Automatic Terraform Apply After CI

This would provide a fully automated deployment model, but every qualifying CI change could modify Azure infrastructure without a separate release decision.

### Manual Terraform Apply Outside the Pipeline

This would provide control but would reduce deployment consistency, traceability, and automation.

## Rationale

The project intentionally separates automatic CI validation from controlled infrastructure deployment.

Using the saved Terraform plan also ensures that the approved deployment corresponds to the plan that was reviewed rather than silently generating a different plan during the Apply stage.

## Consequences

### Positive

* Explicit production approval
* Clear separation between CI and CD
* Better deployment traceability
* Reduced risk of unintended infrastructure changes
* Post-deployment validation provides additional evidence of success

### Negative

* Deployment requires an explicit approval step
* CD is slower than fully automatic deployment
* The Terraform plan artifact must be retained and passed between stages

## Project Evidence

The Azure DevOps CD pipeline uses the `terraform-production` environment for the approval gate. The Apply stage consumes the published Terraform plan artifact and performs post-deployment smoke validation.
