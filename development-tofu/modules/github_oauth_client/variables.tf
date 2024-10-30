variable "github_homepage_url" {
  type        = string
  description = "The URL of the GitHub OAuth app"
  default     = "http://localhost:8000"
}

variable "github_authorization_callback_url" {
  type        = string
  description = "The URL of the GitHub OAuth app callback"
  default     = "http://localhost:8000/accounts/github/login/callback/"
}

variable "github_token" {
  type        = string
  description = "The GitHub token for creating the OAuth app"
}
