resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.project}-${var.env}-redis-subnet"
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "redis" {
  vpc_id = var.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id      = "${var.project}-${var.env}"
  engine          = "redis"
  node_type       = var.node_type
  num_cache_nodes = 1

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [aws_security_group.redis.id]
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.redis.cache_nodes[0].address
}
