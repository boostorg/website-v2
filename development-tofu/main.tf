module "google_oauth_client" {
  source                     = "./modules/google_oauth_client"
  google_cloud_email         = var.google_cloud_email
  google_cloud_project_name  = var.google_cloud_project_name
  google_organization_domain = var.google_organization_domain
}

# can't implement github support at this time, no API available for
# managing oauth. Leaving this here as a breadcrumb for the future.
# module "github_oauth_client" {
#   source = "./modules/github_oauth_client"
# }
