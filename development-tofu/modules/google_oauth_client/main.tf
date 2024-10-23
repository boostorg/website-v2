resource "google_project" "project" {
  project_id = var.google_cloud_project_name
  name       = "Boost Development"
  org_id     = replace(data.google_organization.org.id, "organizations/", "")
  deletion_policy = "DELETE"
}

data "google_organization" "org" {
  domain = var.google_organization_domain
}

resource "google_project_service" "project_service" {
  project = google_project.project.project_id
  service = "iap.googleapis.com"
}

resource "google_iap_brand" "project_brand" {
  support_email     = var.google_cloud_email
  application_title = "Cloud IAP Protected Application for Boost Development"
  project           = google_project_service.project_service.project
}
