terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "6.8.0"
    }
    http = { # needed for github api requests
      source  = "hashicorp/http"
      version = "~> 2.0"
    }
  }
}
