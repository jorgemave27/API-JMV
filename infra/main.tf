module "networking" {
  source  = "./modules/networking"

  project = var.project
  env     = var.env
}

module "rds" {
  source = "./modules/rds"

  project           = var.project
  env               = var.env
  db_instance_class = var.db_instance_class
  db_name           = var.db_name
  db_username       = var.db_username
  db_password       = var.db_password
  subnet_ids        = module.networking.private_subnets
  vpc_id            = module.networking.vpc_id
}

module "redis" {
  source = "./modules/redis"

  project    = var.project
  env        = var.env
  node_type  = var.redis_node_type
  subnet_ids = module.networking.private_subnets
  vpc_id     = module.networking.vpc_id
}
