# Terraform wrapper — always passes the per-env -var-file so a forgotten
# flag can't silently evaluate count-gated resources to their `false`
# defaults (which would mark all of them for destruction in plan; see the
# 2026-04-26 prod near-miss where 9 destroys including the API custom
# domain + IAM roles surfaced from a missing -var-file).
#
# Default env: prod (currently the only live env; dev/staging tfvars are
# in tfvars.archive/ until those envs are reprovisioned).
#
# Usage:
#   make plan                 # ENV=prod implicit
#   make plan ENV=prod        # explicit
#   make apply
#   make fmt validate
#
# To run a raw terraform command with the var-file pre-supplied:
#   make tf CMD="state list"

ENV ?= prod
VAR_FILE := environments/$(ENV)/terraform.tfvars

# Fail fast if the var file is missing — better than silently dropping to
# variable defaults and blowing away [0]-indexed resources in plan.
_check_env:
	@test -f $(VAR_FILE) || { \
		echo "❌ var file not found: $(VAR_FILE)"; \
		echo "   Available envs: $$(ls environments 2>/dev/null | tr '\n' ' ')"; \
		exit 1; \
	}

.PHONY: init plan apply destroy fmt validate tf _check_env

init: _check_env
	terraform init

plan: _check_env
	terraform plan -var-file=$(VAR_FILE) -out=tfplan

# Apply consumes the saved tfplan if present (so reviewer's plan output
# matches what's applied), else falls back to plan-then-apply.
apply: _check_env
	@if [ -f tfplan ]; then \
		echo "→ applying saved tfplan"; \
		terraform apply tfplan && rm -f tfplan; \
	else \
		echo "→ no saved tfplan; running plan+apply with -var-file"; \
		terraform apply -var-file=$(VAR_FILE); \
	fi

destroy: _check_env
	@test "$(ENV)" != "prod" || { \
		echo "❌ refusing to destroy ENV=prod via make; pass -auto-approve to terraform directly if you really mean it"; \
		exit 1; \
	}
	terraform destroy -var-file=$(VAR_FILE)

fmt:
	terraform fmt -recursive

validate:
	terraform validate

# Generic escape hatch: pass an arbitrary terraform subcommand with the
# var-file pre-supplied. Example: `make tf CMD="state rm aws_foo.bar"`.
tf: _check_env
	terraform $(CMD) -var-file=$(VAR_FILE)
