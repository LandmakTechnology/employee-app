region              = "us-east-1"
environment         = "dev"
cluster_name        = "landmark-cluster"
kubernetes_version  = "1.29"

# VPC
vpc_cidr             = "10.0.0.0/16"
availability_zones   = ["us-east-1a", "us-east-1b"]
private_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24"]
public_subnet_cidrs  = ["10.0.101.0/24", "10.0.102.0/24"]

# Node group
node_instance_types = ["t3.medium"]
node_desired_size   = 2
node_min_size       = 1
node_max_size       = 3

# S3
app_bucket_name = "landmark-app-bucket"

# RDS
db_name           = "employees"
db_username       = "landmark_admin"
db_password       = "ChangeMe123!"
db_instance_class = "db.t3.micro"
