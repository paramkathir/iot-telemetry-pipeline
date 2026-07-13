terraform {
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
}

provider "aws" {
  region = "us-east-1"
}

# ---------------------------------------------------------------------------
# 1. DynamoDB table
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "telemetry" {
  name         = "DeviceTelemetryTF"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "DeviceID"
  range_key    = "Timestamp"

  attribute {
    name = "DeviceID"
    type = "S"
  }

  attribute {
    name = "Timestamp"
    type = "N"
  }
}

# ---------------------------------------------------------------------------
# 2. IAM role for Lambda (trust policy lets Lambda assume this role)
# ---------------------------------------------------------------------------
resource "aws_iam_role" "lambda_exec" {
  name = "TelemetryProcessorTF-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Basic CloudWatch Logs permissions (so you can see Lambda logs)
resource "aws_iam_role_policy_attachment" "lambda_basic_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# DynamoDB write permission, scoped to just this table
resource "aws_iam_role_policy" "lambda_dynamodb" {
  name = "TelemetryProcessorTF-dynamodb-access"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem"]
        Resource = aws_dynamodb_table.telemetry.arn
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# 3. Package and deploy the Lambda function
# ---------------------------------------------------------------------------
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/lambda_build/lambda_function.zip"
}

resource "aws_lambda_function" "telemetry_processor" {
  function_name    = "TelemetryProcessorTF"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.13"
  role             = aws_iam_role.lambda_exec.arn
  timeout          = 10
}

# ---------------------------------------------------------------------------
# 4. IoT Core topic rule -> Lambda
# ---------------------------------------------------------------------------
resource "aws_iot_topic_rule" "telemetry_rule" {
  name        = "TelemetryToLambdaTF"
  description = "Routes device/telemetry messages to the TF-managed Lambda"
  enabled     = true
  sql         = "SELECT * FROM 'device/telemetry/tf'"
  sql_version = "2016-03-23"

  lambda {
    function_arn = aws_lambda_function.telemetry_processor.arn
  }
}

# Grant IoT Core permission to invoke this Lambda
resource "aws_lambda_permission" "allow_iot" {
  statement_id  = "AllowIoTInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.telemetry_processor.function_name
  principal     = "iot.amazonaws.com"
  source_arn    = aws_iot_topic_rule.telemetry_rule.arn
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "dynamodb_table_name" {
  value = aws_dynamodb_table.telemetry.name
}

output "lambda_function_name" {
  value = aws_lambda_function.telemetry_processor.function_name
}

output "iot_rule_topic" {
  value = "device/telemetry/tf"
}
