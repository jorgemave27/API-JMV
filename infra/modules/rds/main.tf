resource "aws_db_subnet_group" "this" {
  name       = "${var.project}-${var.env}-db-subnet"
  subnet_ids = var.subnet_ids

  tags = {
    Name = "${var.project}-${var.env}-db-subnet-group"
  }
}

resource "aws_security_group" "db" {
  name        = "${var.project}-${var.env}-db-sg"
  description = "Security group for PostgreSQL"
  vpc_id      = var.vpc_id

  ingress {
    description = "PostgreSQL from VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project}-${var.env}-db-sg"
  }
}

resource "aws_db_instance" "postgres" {
  identifier             = "${var.project}-${var.env}-postgres"
  allocated_storage      = 20
  engine                 = "postgres"
  engine_version         = "16.3"
  instance_class         = var.db_instance_class
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  skip_final_snapshot    = true
  publicly_accessible    = false
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.db.id]

  tags = {
    Name = "${var.project}-${var.env}-postgres"
  }
}
