output "api_url" {
  description = "Public URL of the API."
  value       = module.services.load_balancer_url
}

output "database_endpoint" {
  description = "PostgreSQL endpoint (private)."
  value       = module.database.endpoint
  sensitive   = true
}

output "documents_bucket" {
  description = "S3 bucket holding resumes and screenshots."
  value       = module.documents.bucket_name
}
