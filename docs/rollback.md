# Rollback Procedure

## Purpose

This project uses a **controlled rollback procedure** rather than automated rollback.

Automated rollback is intentionally not implemented because infrastructure changes may have dependencies, destructive actions require review, and an automatic reversal could introduce additional risk.

The rollback process is:

```text
Identify issue
    ↓
Git revert
    ↓
CI validation
    ↓
Terraform plan
    ↓
Approval
    ↓
Terraform apply
    ↓
Post-deployment smoke test
```

## 1. Identify the Deployment Issue

Confirm that the problem is related to the latest application or infrastructure change.

Review:

* Azure DevOps pipeline results
* Terraform plan and apply output
* Azure resource provisioning state
* Post-deployment smoke validation
* Application or data-platform validation results

Do not immediately apply another change without first identifying the configuration or code change that introduced the issue.

## 2. Revert the Git Change

Create a new revert commit rather than rewriting shared branch history.

Example:

```bash
git log --oneline
git revert <commit>
git push origin main
```

Select the specific commit to revert based on the deployment issue being investigated.

## 3. CI Validation

The reverted commit runs through the normal CI process.

CI validates:

* Python syntax
* ML feature engineering
* ML feature contract consistency
* Data-quality expectations
* Model smoke tests
* Terraform validation
* Terraform plan

The rollback should not proceed until CI succeeds.

## 4. Review the Terraform Plan

Review the generated Terraform plan carefully.

Confirm that the plan represents the intended infrastructure state after the Git revert.

Pay particular attention to:

* Resource creation
* Resource modification
* Resource replacement
* Resource deletion
* Security-related changes
* Networking changes
* Data-platform resources

The Terraform plan should be reviewed before approval.

## 5. Approval

Terraform Apply is protected by the Azure DevOps production environment approval.

A reviewer must approve the rollback deployment before infrastructure changes are applied.

## 6. Terraform Apply

After approval, the pipeline applies the reviewed Terraform plan.

The pipeline uses the published Terraform plan artifact rather than generating a new plan during the Apply stage.

This keeps the reviewed plan and applied plan aligned.

## 7. Post-Deployment Smoke Test

After Terraform Apply completes, the CD pipeline runs the post-deployment smoke validation.

The smoke validation confirms:

* Azure authentication succeeds
* The target resource group exists
* Deployed Azure resources are discoverable
* Resource provisioning states are reported

If the smoke validation fails, stop further deployment activity and investigate before making additional changes.

## 8. Manual Recovery

If the rollback does not restore the expected state, investigate the Terraform state and Azure resource configuration before taking further action.

Do not repeatedly apply Terraform changes without first understanding the resulting Terraform plan.

## Why Automated Rollback Is Not Used

This project deliberately does not implement automatic rollback.

Infrastructure rollback can involve resource replacement, deletion, state changes, data dependencies, and security configuration. Automatically reversing these changes could create additional risk.

A controlled rollback provides:

* Human review
* Auditable Git history
* A reviewed Terraform plan
* Protected production approval
* Post-deployment validation

This approach provides a controlled and auditable rollback process while avoiding unnecessary automated infrastructure reversal.
