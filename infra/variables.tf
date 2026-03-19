variable "region" {
  type        = string
  description = "AWS region"
}

variable "env" {
  type        = string
  description = "Environment (dev/prod)"
}

variable "project" {
  type        = string
  description = "Project name"
  default     = "api-jmv"
}

variable "db_instance_class" {
  type        = string
  description = "RDS instance class"
}

variable "redis_node_type" {
  type        = string
  description = "ElastiCache node type"
}

variable "db_name" {
  type        = string
  description = "PostgreSQL database name"
  default     = "apijmv"
}

variable "db_username" {
  type        = string
  description = "PostgreSQL master username"
  default     = "postgres"
}

variable "db_password" {
  type        = string
  description = "PostgreSQL master password"
  sensitive   = true
}
