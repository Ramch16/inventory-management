variable "project" {
  description = "Name prefix for every resource."
  type        = string
  default     = "jobapply"
}

variable "environment" {
  description = "Deployment environment (staging, production)."
  type        = string
}

variable "region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "database_instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "worker_desired_count" {
  type    = number
  default = 2
}

variable "automation_desired_count" {
  description = "Browser workers. Each holds Chromium in memory, so scale deliberately."
  type        = number
  default     = 1
}

variable "domain_name" {
  type    = string
  default = null
}
