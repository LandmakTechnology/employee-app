# Cluster outputs
output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "cluster_name" {
  value = module.eks.cluster_name
}

output "app_bucket_name" {
  value = aws_s3_bucket.app.bucket
}

output "s3_access_role_arn" {
  description = "Service account role ARN (S3 + Secrets Manager + ECR)"
  value       = module.app_irsa.iam_role_arn
}

output "lb_controller_role_arn" {
  value = module.lb_controller_irsa.iam_role_arn
}

output "kubeconfig_command" {
  value = "aws eks update-kubeconfig --name ${var.cluster_name}-${var.environment} --region ${var.region} --profile terraform"
}

# RDS outputs
output "rds_endpoint" {
  value = aws_db_instance.main.endpoint
}

output "rds_address" {
  value = aws_db_instance.main.address
}

# ECR outputs
output "ecr_backend_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_url" {
  value = aws_ecr_repository.frontend.repository_url
}

# Secrets Manager outputs
output "secrets_manager_secret_arn" {
  value = aws_secretsmanager_secret.db_credentials.arn
}
