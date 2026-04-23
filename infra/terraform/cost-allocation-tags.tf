# Story 9.7 — Cost-allocation tag activation.
#
# AWS cost-allocation tags are only visible to the Billing console / Cost
# Explorer AFTER they are activated at the management-account level. Stamping
# them via provider default_tags (providers.tf) is necessary but not sufficient
# — without activation, the tags appear on resources but not in billing data.
# aws_ce_cost_allocation_tag automates that activation. It is:
#   - account-global (no region, no environment)
#   - idempotent per tag key
#   - takes effect on usage AFTER activation (no retroactive tagging)
#
# The pre-existing tags Project / Environment / ManagedBy are NOT re-activated
# here — they were activated manually when the 1.x infra went live, and
# re-declaring them in Terraform would either error on "already active" or
# silently succeed depending on provider behaviour. Neither is worth the risk.
# Only the three NEW tag keys introduced by Story 9.7's default_tags block
# (feature / epic / env) are activated here.

resource "aws_ce_cost_allocation_tag" "feature" {
  tag_key = "feature"
  status  = "Active"
}

resource "aws_ce_cost_allocation_tag" "epic" {
  tag_key = "epic"
  status  = "Active"
}

resource "aws_ce_cost_allocation_tag" "env" {
  tag_key = "env"
  status  = "Active"
}
