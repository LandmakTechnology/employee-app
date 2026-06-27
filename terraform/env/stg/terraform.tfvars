region              = "us-east-1"
environment         = "stg"
cluster_name        = "landmark-cluster"
kubernetes_version  = "1.29"

# VPC
vpc_cidr             = "10.1.0.0/16"
availability_zones   = ["us-east-1a", "us-east-1b", "us-east-1c"]
private_subnet_cidrs = ["10.1.1.0/24", "10.1.2.0/24", "10.1.3.0/24"]
public_subnet_cidrs  = ["10.1.101.0/24", "10.1.102.0/24", "10.1.103.0/24"]

# Node group
node_instance_types = ["t3.medium"]
node_desired_size   = 2
node_min_size       = 2
node_max_size       = 5

# S3
app_bucket_name = "landmark-app-bucket"

# RDS
db_name           = "employees"
db_username       = "landmark_admin"
db_password       = "ChangeMe123!"
db_instance_class = "db.t3.small"
