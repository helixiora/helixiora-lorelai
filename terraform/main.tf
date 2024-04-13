terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 3.0"
    }
  }
  required_version = ">= 0.12"
}

provider "aws" {
  region = "eu-west-1"
}

variable "project_name" {
  description = "Name for the project to create resources"
  default     = "helixiora-lorelai-manual"
}

# Secrets Manager for GitHub credentials
resource "aws_secretsmanager_secret" "github_token" {
  name        = "${var.project_name}-github-token"
  description = "GitHub token for accessing private Docker images"
}

resource "aws_secretsmanager_secret_version" "github_token_version" {
  secret_id     = aws_secretsmanager_secret.github_token.id
  secret_string = jsonencode({
    username = "your-github-username"  # Replace with your GitHub username
    password = "your-github-access-token"  # Replace with your GitHub access token
  })
}

# IAM Role for ECS Task Execution
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.project_name}-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      },
    ]
  })
}

resource "aws_iam_policy" "secrets_access" {
  name        = "${var.project_name}-secrets-access"
  description = "Allow access to secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ],
        Resource = "*",
        Effect   = "Allow"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "secrets_access_attachment" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = aws_iam_policy.secrets_access.arn
}

# ECS Cluster
resource "aws_ecs_cluster" "app_cluster" {
  name = "${var.project_name}-cluster"
}

# ECS Task Definition for Web Service
resource "aws_ecs_task_definition" "web" {
  family                   = "${var.project_name}-web"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn

  container_definitions = jsonencode([
    {
      name      = "web"
      image     = "ghcr.io/helixiora/helixiora-lorelai/web:latest"
      cpu       = 256
      memory    = 512
      essential = true
      portMappings = [
        {
          containerPort = 5000
          hostPort      = 5000
          protocol      = "tcp"
        }
      ],
      environment = [
        { name = "FLASK_APP", value = "run.py" },
        { name = "REDIS_URL", value = "redis://redis:6379/0" }
      ],
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = "/ecs/${var.project_name}"
          awslogs-region        = "eu-west-1"
          awslogs-stream-prefix = "ecs"
        }
      },
      secrets = [
        {
          name      = "username",
          valueFrom = "${aws_secretsmanager_secret.github_token.id}:username::"
        },
        {
          name      = "password",
          valueFrom = "${aws_secretsmanager_secret.github_token.id}:password::"
        }
      ]
    }
  ])
}

# Application Load Balancer, Listener, and Target Group
resource "aws_alb" "app_lb" {
  name               = "${var.project_name}-lb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = [subnet_id_1, subnet_id_2]  # Specify your subnet IDs
  enable_deletion_protection = false
}

resource "aws_alb_listener" "front_end" {
  load_balancer_arn = aws_alb.app_lb.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_alb_target_group.app_tg.arn
  }
}

resource "aws_alb_target_group" "app_tg" {
  name     = "${var.project_name}-tg"
  port     = 5000
  protocol = "HTTP"
  vpc_id   = vpc_id  # Specify your VPC ID
}

# Security Group for ALB
resource "aws_security_group" "alb_sg" {
  name        = "${var.project_name}-alb-sg"
  description = "Allow web traffic to ALB"
  vpc_id      = vpc_id  # Specify your VPC ID

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Route 53 DNS Configuration
resource "aws_route53_record" "app_dns" {
  zone_id = aws_route53_zone.app_zone.zone_id
  name    = "lorelai.helixiora.com"
  type    = "A"

  alias {
    name                   = aws_alb.app_lb.dns_name
    zone_id                = aws_alb.app_lb.zone_id
    evaluate_target_health = true
  }
}

output "alb_dns_name" {
  value = aws_alb.app_lb.dns_name
}
