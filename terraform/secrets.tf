# AWS Secrets Manager secret for RDS credentials
resource "aws_secretsmanager_secret" "db_credentials" {
  name = "${var.cluster_name}-${var.environment}/employee-app"

  tags = {
    Name        = "${var.cluster_name}-${var.environment}/employee-app"
    Environment = var.environment
  }
}

# Store RDS credentials as JSON in Secrets Manager
resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id

  secret_string = jsonencode({
    db_host      = aws_db_instance.main.address
    db_port      = "5432"
    db_name      = var.db_name
    db_username  = var.db_username
    db_password  = var.db_password
    database_url = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.main.address}:5432/${var.db_name}"
  })
}

# IAM policy for Secrets Manager access (used by External Secrets Operator via IRSA)
resource "aws_iam_policy" "secrets_access" {
  name = "${var.cluster_name}-${var.environment}-secrets-access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
          "secretsmanager:ListSecrets"
        ]
        Resource = [
          aws_secretsmanager_secret.db_credentials.arn,
          "${aws_secretsmanager_secret.db_credentials.arn}*"
        ]
      }
    ]
  })
}
