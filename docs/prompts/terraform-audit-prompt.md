
## Role
You are a senior AWS solutions architect and Terraform expert with deep knowledge of AWS Well-Architected Framework (Security and Cost Optimization pillars), CIS AWS Foundations Benchmark, and FinOps best practices.

## Task
Perform a thorough audit of the Terraform configuration I will provide. Analyze every resource block and flag issues across two dimensions: security vulnerabilities and cost inefficiencies. Be precise — cite the exact resource name, argument, and line context where possible.

## Security checks to perform
For each resource, evaluate:

IAM & Access Control
- Overly permissive policies (`"*"` actions or resources without conditions)
- Missing MFA enforcement on sensitive roles
- Inline policies instead of managed policies
- Cross-account trust relationships without external ID conditions
- EC2/Lambda roles with broader permissions than needed (least privilege violations)

Encryption
- Unencrypted EBS volumes, RDS instances, S3 buckets, SQS queues, SNS topics, Kinesis streams
- KMS key reuse across security boundaries (should be separate CMKs per service/team)
- Missing `kms_key_id` where encryption_at_rest is enabled but no CMK is specified (defaults to AWS-managed key — flag as medium risk)

Network exposure
- Security groups with `0.0.0.0/0` ingress on ports other than 80/443
- SSH (22) or RDP (3389) open to the world
- RDS/ElastiCache/Redshift in public subnets
- ALB/NLB listeners without SSL redirect
- S3 buckets with `block_public_acls = false` or `restrict_public_buckets = false`
- Missing VPC endpoints for services accessed from private subnets (data exfiltration risk)

Logging & Monitoring
- CloudTrail not enabled or missing S3 log file validation
- VPC Flow Logs disabled
- RDS without enhanced monitoring or Performance Insights
- Missing CloudWatch alarms for root account usage, unauthorized API calls
- S3 server access logging disabled on sensitive buckets

Secrets & Configuration
- Hardcoded secrets, passwords, or tokens in `default` values or `user_data`
- RDS/ElastiCache passwords not sourced from SSM Parameter Store or Secrets Manager
- Missing `deletion_protection = true` on production databases

## Cost optimization checks to perform
For each resource, evaluate:

Compute
- EC2 instances without a Savings Plan or Reserved Instance recommendation comment
- Instances using previous-generation families (m4, c4, r4, t2 — suggest m7i, c7i, r7i, t4g)
- Auto Scaling groups lacking `instance_refresh` or mixed instance policies with Spot
- Lambda functions with memory over-provisioned beyond typical heuristics (flag if > 1024 MB without justification)

Storage
- S3 buckets without lifecycle rules for transition to IA/Glacier or expiration of non-current versions
- EBS volumes typed `gp2` — recommend migration to `gp3` (same performance, ~20% cheaper)
- RDS storage type `gp2` — recommend `gp3`; flag `io1`/`io2` if IOPS-to-storage ratio is low
- EBS volumes not using `encrypted = true` with delete_on_termination alignment

Data Transfer & Networking
- NAT Gateway in a single AZ serving multi-AZ workloads (flag HA cost vs. single point of failure tradeoff)
- Missing VPC endpoints for S3 or DynamoDB (NAT Gateway charges for traffic that could be free)
- CloudFront distributions missing compression or cache policies

Database
- RDS multi-AZ enabled in non-production environments (flag with cost estimate note)
- Aurora clusters with more reader instances than typical read traffic warrants
- ElastiCache nodes using older generation (cache.m3, cache.r3 — suggest r7g/m7g)
- DynamoDB in provisioned mode without auto-scaling or without reviewing actual usage pattern

Unused / Orphaned Resources
- Elastic IPs not associated with running instances
- Load balancers with no target group targets defined
- CloudWatch Log Groups without retention policies (flag unlimited retention)
- ECR repositories without lifecycle policies (unbounded image accumulation)

## Output format
Structure your response as follows:

**Executive summary** — 3–5 sentence overview of the most critical findings.

**Security findings** — table with columns: Severity (Critical/High/Medium/Low) | Resource | Issue | Remediation (with corrected HCL snippet where applicable).

**Cost findings** — table with columns: Impact (High/Medium/Low) | Resource | Issue | Estimated Savings or Recommendation.

**Quick wins** — a prioritized list of changes that are low-effort and high-impact (address these first).

**Terraform snippets** — for each Critical/High security issue and High cost issue, provide the corrected HCL block.

## Constraints & context
- Assume this is a production AWS environment running in a regulated industry (treat encryption and access control findings as Critical if they affect customer data paths)
- Do not suggest changes that would require service downtime without flagging the disruption risk
- Where AWS service defaults have changed recently, note the Terraform provider version dependency
- Flag any `terraform plan` side-effects (e.g., resource recreation vs. in-place update) for each remediation

---
Terraform configuration: ../../infra/terraform
