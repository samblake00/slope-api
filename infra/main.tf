terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  # Bucket/key/region are passed with -backend-config (see README)
  backend "s3" {}
}

provider "aws" {
  region = var.region
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "name" {
  type    = string
  default = "slope-api"
}

variable "database_url" {
  type        = string
  sensitive   = true
  description = "Postgres URL, e.g. postgresql://user:pass@host/db?sslmode=require"
}

variable "poll_rate" {
  type    = string
  default = "rate(1 day)"
}

variable "poll_batch_size" {
  type        = number
  default     = 4000
  description = "Max resorts refreshed per poll; Open-Meteo's free tier allows 10,000 locations/day"
}

variable "api_reserved_concurrency" {
  type        = number
  default     = -1
  description = "Caps concurrent API invocations (and DB connections). -1 = unreserved. New AWS accounts often can't reserve any until their concurrency quota is raised."
}

variable "throttle_rate_limit" {
  type    = number
  default = 10
}

variable "throttle_burst_limit" {
  type    = number
  default = 20
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../build"
  output_path = "${path.module}/lambda.zip"
}

resource "aws_iam_role" "lambda" {
  name = "${var.name}-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

locals {
  environment = {
    APP_CONFIG      = "config.ProductionConfig"
    DATABASE_URL    = var.database_url
    POLL_BATCH_SIZE = tostring(var.poll_batch_size)
  }
}

resource "aws_lambda_function" "api" {
  function_name                  = "${var.name}-api"
  role                           = aws_iam_role.lambda.arn
  runtime                        = "python3.12"
  architectures                  = ["arm64"]
  handler                        = "lambda_handlers.api_handler"
  filename                       = data.archive_file.lambda.output_path
  source_code_hash               = data.archive_file.lambda.output_base64sha256
  memory_size                    = 256
  timeout                        = 29
  reserved_concurrent_executions = var.api_reserved_concurrency

  environment {
    variables = local.environment
  }
}

resource "aws_lambda_function" "poller" {
  function_name    = "${var.name}-poller"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  architectures    = ["arm64"]
  handler          = "lambda_handlers.poller_handler"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  memory_size      = 256
  timeout          = 600

  environment {
    variables = local.environment
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${aws_lambda_function.api.function_name}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "poller" {
  name              = "/aws/lambda/${aws_lambda_function.poller.function_name}"
  retention_in_days = 14
}

# HTTP API in front of the API function
resource "aws_apigatewayv2_api" "http" {
  name          = var.name
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true

  # Hard global ceiling; Flask-Limiter handles per-IP limits
  default_route_settings {
    throttling_rate_limit  = var.throttle_rate_limit
    throttling_burst_limit = var.throttle_burst_limit
  }
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowHttpApi"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

# EventBridge schedule for the poller
resource "aws_cloudwatch_event_rule" "poll" {
  name                = "${var.name}-poll"
  schedule_expression = var.poll_rate
}

resource "aws_cloudwatch_event_target" "poll" {
  rule = aws_cloudwatch_event_rule.poll.name
  arn  = aws_lambda_function.poller.arn
}

resource "aws_lambda_permission" "events" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.poller.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.poll.arn
}

output "api_url" {
  value = "${aws_apigatewayv2_api.http.api_endpoint}/api/v1"
}
