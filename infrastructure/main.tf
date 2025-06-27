# main.tf
terraform {
  required_providers {
    aws = { source = "hashicorp/aws" }
  }
}

provider "aws" {
  region = "us-east-1"
}

# 1. ECR Repository
resource "aws_ecr_repository" "options_pricing" {
  name = "options_pricing"
  force_delete = true
}
resource "aws_ecr_repository" "worker" {
  name         = "options-pricing-worker"
  force_delete = true
}

# 2. Build & Push Docker Image (use Dockerfile.lambda)
resource "null_resource" "docker_deploy" {
  depends_on = [aws_ecr_repository.options_pricing]
  provisioner "local-exec" {
    command = <<-EOC
      # Log in to ECR
      aws ecr get-login-password --region us-east-1 \
        | docker login --username AWS --password-stdin ${aws_ecr_repository.options_pricing.repository_url}

      # Build and push image using Dockerfile.lambda
      # Dockerfile.lambda and code are one level up
      docker build --platform linux/amd64 \
        -f ../Dockerfile.submitter \
        -t ${aws_ecr_repository.options_pricing.repository_url}:latest \
        ..
        -f ../Dockerfile.submitter \
        -t ${aws_ecr_repository.options_pricing.repository_url}:latest \
        ..

      docker push ${aws_ecr_repository.options_pricing.repository_url}:latest
    EOC
    interpreter = ["bash", "-c"]
  }
}
resource "null_resource" "docker_worker" {
  depends_on = [aws_ecr_repository.worker]
  provisioner "local-exec" {
    command = <<-EOC
      aws ecr get-login-password --region us-east-1 \
        | docker login --username AWS --password-stdin ${aws_ecr_repository.worker.repository_url}
      docker build --platform linux/amd64 -f ../Dockerfile.worker \
        -t ${aws_ecr_repository.worker.repository_url}:latest \
        ..
        -f ../Dockerfile.worker \
        -t ${aws_ecr_repository.worker.repository_url}:latest \
        ..

      docker push ${aws_ecr_repository.worker.repository_url}:latest
    EOC
    interpreter = ["bash", "-c"]
  }
}

# 3. IAM Role for Lambda
resource "aws_iam_role" "lambda_exec" {
  name = "lambda-ecr-exec-role-v2"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "lambda.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "ecr_read" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}
resource "aws_iam_role_policy_attachment" "sqs_dynamo" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
}
resource "aws_iam_role_policy_attachment" "sqs_read" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSQSFullAccess"
}

#--- SQS Queue & DynamoDB Table ---
resource "aws_sqs_queue" "jobs" {
  name                      = "options-pricing-jobs"
  visibility_timeout_seconds = 900
}
resource "aws_dynamodb_table" "results" {
  name         = "options-pricing-results"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "jobId"

  attribute {
    name = "jobId"
    type = "S"
  }
  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }
}

# 4. Lambda Function
resource "aws_lambda_function" "options_pricing" {
  depends_on    = [null_resource.docker_deploy]
  function_name = "pricingApiFunction"
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.options_pricing.repository_url}:latest"
  role          = aws_iam_role.lambda_exec.arn
  timeout       = 30
  memory_size   = 512

  environment {
    variables = {
      JOB_QUEUE_URL  = aws_sqs_queue.jobs.id
      RESULTS_TABLE  = aws_dynamodb_table.results.name
    }
  }
}


resource "aws_lambda_function" "worker" {
  depends_on    = [null_resource.docker_worker]
  function_name = "options-pricing-worker"
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.worker.repository_url}:latest"
  role          = aws_iam_role.lambda_exec.arn
  timeout       = 900
  memory_size   = 1024

  environment {
    variables = {
      JOB_QUEUE_URL = aws_sqs_queue.jobs.id
      RESULTS_TABLE = aws_dynamodb_table.results.name
    }
  }
}
#--- SQS -> Worker Event Source Mapping ---
resource "aws_lambda_event_source_mapping" "worker_map" {
  event_source_arn  = aws_sqs_queue.jobs.arn
  function_name     = aws_lambda_function.worker.arn
  batch_size        = 1
}


# 5. API Gateway HTTP API
resource "aws_apigatewayv2_api" "options_pricing" {
  name          = "PricingApi"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id             = aws_apigatewayv2_api.options_pricing.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.options_pricing.invoke_arn
  integration_method = "POST"
}

resource "aws_apigatewayv2_route" "catch_all" {
  api_id    = aws_apigatewayv2_api.options_pricing.id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

resource "aws_lambda_permission" "allow_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.options_pricing.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.options_pricing.execution_arn}/*/*"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.options_pricing.id
  name        = "$default"
  auto_deploy = true
}

# 6. Public Endpoint Output
output "api_endpoint" {
  value = aws_apigatewayv2_stage.default.invoke_url
  description = "Invoke URL for the deployed API"
}

output "sqs_queue_url" {
  value       = aws_sqs_queue.jobs.id
  description = "SQS queue URL for job submissions"
}
output "dynamodb_table" {
  value       = aws_dynamodb_table.results.name
  description = "DynamoDB table for results"
}
