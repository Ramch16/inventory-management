# Terraform skeleton

A starting point, not a turnkey deployment: the modules describe the shape of the AWS
environment the platform expects, with the security decisions made explicitly. Fill in
the variables for your account and review every resource before applying.

```
terraform init
terraform plan  -var-file=env/staging.tfvars
terraform apply -var-file=env/staging.tfvars
```

## What it provisions

| Resource | Why |
| --- | --- |
| VPC with private subnets | Database and cache are never publicly reachable |
| RDS PostgreSQL | Encrypted at rest, automated backups, private subnet group |
| ElastiCache Redis | Broker and cache, private, encrypted in transit |
| S3 bucket | Resumes and screenshots: private, versioned, SSE, public access blocked |
| Secrets Manager | `SECRET_KEY`, provider API keys — never in task definitions |
| ECS services | `api`, `worker`, `automation` (Chromium), `beat` |
| ALB | TLS termination, HTTP redirected to HTTPS |
| CloudWatch log groups | Structured JSON logs with a retention policy |

## Decisions worth keeping

* The automation service runs as its own task definition, so the browser image and its
  memory profile never affect the API.
* The S3 bucket blocks all public access; documents are served through short-lived
  presigned URLs issued by the API after an authorization check.
* Secrets are injected from Secrets Manager at task start; nothing sensitive appears in
  a task definition, an image, or an environment file in the repository.
