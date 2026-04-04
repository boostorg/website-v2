"""GraphQL queries for GitHub API.

Query limits tuned based on analysis of 16,851 PRs and 14,647 issues (as of 2026-02-17).
See analysis scripts: /tmp/check_pr_complexity.py, /tmp/check_actual_pr_threads.py
"""

# Pull Request Queries

PR_CONTRIBUTIONS_QUERY = """
query GetPRContributions($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequests(first: 50, after: $cursor, orderBy: {field: UPDATED_AT, direction: ASC}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        number
        title
        body
        createdAt
        updatedAt
        author {
          ... on User {
            databaseId
            login
          }
        }
        timelineItems(first: 100, itemTypes: [
          ISSUE_COMMENT,
          CLOSED_EVENT,
          MERGED_EVENT,
          REOPENED_EVENT
        ]) {
          # Observed: avg 3.2/PR, p90: 7, p99: 24, max: 100
          # Data loss: 1 PR hit this limit (math#400 with 100 timeline items)
          # PRs with >100 timeline items will have truncated comment/event history
          nodes {
            __typename
            ... on IssueComment {
              id
              body
              createdAt
              author {
                ... on User {
                  databaseId
                  login
                }
              }
            }
            ... on ClosedEvent {
              id
              createdAt
              actor {
                ... on User {
                  databaseId
                  login
                }
              }
            }
            ... on MergedEvent {
              id
              createdAt
              actor {
                ... on User {
                  databaseId
                  login
                }
              }
            }
          }
        }
        reviewThreads(first: 100) {
          # Observed: avg 70.4 threads/PR, max: 144 threads (url#229)
          # GitHub limit: Hard limit of 100, cannot be increased
          # Data loss: 3 PRs exceed this limit (url#229: 144, ublas#80: 92, ublas#90: 55)
          # Missing ~112 comments total across these PRs
          # PRs with >100 review threads will have truncated code review history
          nodes {
            comments(first: 50) {
              # Observed: avg 2.5 comments/thread, max: 28 comments/thread
              # Data loss: None expected (max observed well under limit)
              # Threads with >50 comments will be truncated (not observed in dataset)
              nodes {
                __typename
                ... on PullRequestReviewComment {
                  id
                  body
                  createdAt
                  author {
                    ... on User {
                      databaseId
                      login
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

# Note: GitHub's GraphQL API does not support filterBy on pullRequests field,
# so PR queries cannot be filtered server-side like issues can be.

# Issue Queries

ISSUE_CONTRIBUTIONS_QUERY = """
query GetIssueContributions($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    issues(first: 100, after: $cursor, orderBy: {field: UPDATED_AT, direction: ASC}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        number
        title
        body
        createdAt
        author {
          ... on User {
            databaseId
            login
          }
        }
        timelineItems(first: 10, itemTypes: [
          CLOSED_EVENT,
          REOPENED_EVENT
        ]) {
          # Observed: avg 0.4 events/issue, max: 4 events
          # Data loss: None (max observed well under limit)
          # Issues with >10 close/reopen events will be truncated (extremely rare)
          nodes {
            __typename
            ... on ClosedEvent {
              id
              createdAt
              actor {
                ... on User {
                  databaseId
                  login
                }
              }
            }
            ... on ReopenedEvent {
              id
              createdAt
              actor {
                ... on User {
                  databaseId
                  login
                }
              }
            }
          }
        }
        comments(first: 50) {
          # Observed: avg 3.8 comments/issue, p90: 9, p95: 13, p99: 25, max: 100
          # Data loss: 1 issue at limit (beast#154 with 100 comments)
          # Issues with >50 comments will have truncated discussion history
          nodes {
            id
            body
            createdAt
            author {
              ... on User {
                databaseId
                login
              }
            }
          }
        }
      }
    }
  }
}
"""

ISSUE_CONTRIBUTIONS_QUERY_WITH_FILTER = """
query GetIssueContributions($owner: String!, $repo: String!, $cursor: String, $since: DateTime!) {
  repository(owner: $owner, name: $repo) {
    issues(first: 100, after: $cursor, orderBy: {field: UPDATED_AT, direction: ASC}, filterBy: {since: $since}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        number
        title
        body
        createdAt
        author {
          ... on User {
            databaseId
            login
          }
        }
        timelineItems(first: 10, itemTypes: [
          CLOSED_EVENT,
          REOPENED_EVENT
        ]) {
          # Observed: avg 0.4 events/issue, max: 4 events
          # Data loss: None (max observed well under limit)
          # Issues with >10 close/reopen events will be truncated (extremely rare)
          nodes {
            __typename
            ... on ClosedEvent {
              id
              createdAt
              actor {
                ... on User {
                  databaseId
                  login
                }
              }
            }
            ... on ReopenedEvent {
              id
              createdAt
              actor {
                ... on User {
                  databaseId
                  login
                }
              }
            }
          }
        }
        comments(first: 50) {
          # Observed: avg 3.8 comments/issue, p90: 9, p95: 13, p99: 25, max: 100
          # Data loss: 1 issue at limit (beast#154 with 100 comments)
          # Issues with >50 comments will have truncated discussion history
          nodes {
            id
            body
            createdAt
            author {
              ... on User {
                databaseId
                login
              }
            }
          }
        }
      }
    }
  }
}
"""
