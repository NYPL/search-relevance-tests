terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }

  backend "s3" {
    bucket  = "nypl-github-actions-builds-qa"
    key     = "search-relevance-tests-state"
    region  = "us-east-1"
  }
}

provider "aws" {
  region = "us-east-1"
}


variable "environment" {
  type = string
  default = "qa"
  description = "The name of the environment (qa, production). This controls the name of lambda and the env vars loaded."

  validation {
    condition     = contains(["qa", "production"], var.environment)
    error_message = "The environmet must be 'qa' or 'production'."
  }
}

data "aws_ecr_repository" "ecr_repo" {
  name = "search-relevance-tests"
}

data "external" "git" {
  program = [
    "git",
    "log",
    "--pretty=format:{ \"sha\": \"%H\" }",
    "-1",
    "HEAD"
  ]
}

resource "aws_lambda_function" "function" {
  function_name = "SearchRelevanceTests-${var.environment}"
  timeout       = 900 # seconds
  image_uri     = "${data.aws_ecr_repository.ecr_repo.repository_url}:${var.environment}"
  memory_size   = 1024
  package_type  = "Image"

  role          = "arn:aws:iam::946183545209:role/lambda-full-access"

  source_code_hash = data.external.git.result.sha

  vpc_config {
    # FIXME: These are just for QA:
    subnet_ids         = ["subnet-21a3b244", "subnet-f35de0a9"]
    security_group_ids = ["sg-aa74f1db"]
  }

  environment {
    variables = {
      ENVIRONMENT = var.environment
    }
  }
}

