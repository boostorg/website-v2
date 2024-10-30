variable "google_cloud_email" {
  type        = string
  description = "The email address of the Google Cloud user"
}

variable "google_cloud_project_name" {
  type        = string
  description = "The project name for the Google Cloud project"
  default     = "localboostdev"
}

variable "google_organization_domain" {
  type        = string
  description = "The domain of the Google Cloud organization"
}
