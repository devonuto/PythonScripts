#
# Copyright (c) nexB Inc. and others. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# See http://www.apache.org/licenses/LICENSE-2.0 for the license text.
# See https://aboutcode.org for more information about nexB OSS projects.
#


import getpass
from traceback import format_exc as traceback_format_exc

import requests

# Can be 'ORGANIZATION' or 'USER'
SOURCE_ACCOUNT_TYPE = "USER"
SOURCE_ACCOUNT_NAME = "devonuto"

TARGET_ACCOUNT_TYPE = "ORGANIZATION"
TARGET_ACCOUNT_NAME = "Old-Man-Footy"


GITHUB_TOKEN = None


def get_github_api():
    global GITHUB_TOKEN
    if not GITHUB_TOKEN:
        GITHUB_TOKEN = getpass.getpass(
            prompt="Enter your GitHub API (With permission to write projects): "
        )
    


def graphql_query(query, variables=None):
    url = "https://api.github.com/graphql"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    response = requests.post(url, headers=headers, json={"query": query, "variables": variables})

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(
            f"Query failed with status code {response.status_code}. Response: {response.text}"
        )


def fetch_project_node_id(account_type, account_name, project_number):
    query = f"""
    query {{
        {account_type.lower()}(login: "{account_name}") {{
            projectV2(number: {project_number}) {{
                id
            }}
        }}
    }}
    """
    data = graphql_query(query)
    return data["data"][account_type.lower()]["projectV2"]["id"]


def get_project_name(project_id):
    """Fetch name of a GitHub project given its ID."""
    query = """
    query($id: ID!) {
      node(id: $id) {
        ... on ProjectV2 {
          title
          number
        }
      }
    }
    """
    data = graphql_query(query, variables={"id": project_id})
    project_name = data["data"]["node"]["title"]
    if project_name:
        return project_name
    else:
        return "Project not found or does not exist."


def fetch_all_project_items(project_id):
    all_items = []
    has_next_page = True
    cursor = None

    while has_next_page:
        query = """
        query($projectId: ID!, $cursor: String) {
            node(id: $projectId) {
                ... on ProjectV2 {
                    items(first: 100, after: $cursor) {
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                        nodes {
                            id
                            content {
                                ... on DraftIssue {
                                    title
                                    body
                                }
                                ... on Issue {
                                    title
                                    url
                                    id
                                    assignees(first: 10) {
                                        nodes {
                                            login
                                        }
                                    }
                                }
                                ... on PullRequest {
                                    title
                                    url
                                    id
                                    assignees(first: 10) {
                                        nodes {
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
        """
        variables = {"projectId": project_id, "cursor": cursor}
        data = graphql_query(query, variables)
        items = data["data"]["node"]["items"]
        all_items.extend(items["nodes"])
        page_info = items["pageInfo"]
        has_next_page = page_info["hasNextPage"]
        cursor = page_info["endCursor"]

    return all_items


def create_new_project(owner_id, project_name):
    query = """
    mutation($ownerId: ID!, $title: String!) {
        createProjectV2(input: {ownerId: $ownerId, title: $title}) {
            projectV2 {
                id
            }
        }
    }
    """
    variables = {"ownerId": owner_id, "title": project_name}
    data = graphql_query(query, variables)
    return data["data"]["createProjectV2"]["projectV2"]["id"]


def add_item_to_project(project_id, content_id):
    query = """
    mutation($projectId: ID!, $contentId: ID!) {
        addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
            item {
                id
            }
        }
    }
    """
    variables = {"projectId": project_id, "contentId": content_id}
    data = graphql_query(query, variables)
    if data.get("data", {}).get("addProjectV2ItemById") is None:
        raise Exception(f"Could not add item with ID {content_id} to project {project_id}.")
    return data["data"]["addProjectV2ItemById"]["item"]["id"]


def create_draft_issue_in_project(project_id, title, body):
    query = """
    mutation($projectId: ID!, $title: String!, $body: String!) {
        addProjectV2DraftIssue(input: {projectId: $projectId, title: $title, body: $body}) {
            projectItem {
                id
            }
        }
    }
    """
    variables = {"projectId": project_id, "title": title, "body": body}
    data = graphql_query(query, variables)
    if data.get("data", {}).get("addProjectV2DraftIssue") is None:
        raise Exception(f"Could not create draft issue with title {title} in project {project_id}.")
    return data["data"]["addProjectV2DraftIssue"]["projectItem"]["id"]


def get_account_id(account_type, account_name):
    query = f"""
    query {{
        {account_type.lower()}(login: "{account_name}") {{
            id
        }}
    }}
    """
    data = graphql_query(query)
    return data["data"][account_type.lower()]["id"]


def get_project_url(project_id, account_type, account_name):
    query = """
    query($id: ID!) {
      node(id: $id) {
        ... on ProjectV2 {
          title
          number
        }
      }
    }
    """
    data = graphql_query(query, variables={"id": project_id})
    number = data["data"]["node"]["number"]

    a_type = "users" if account_type == "USER" else "orgs"

    return f"https://github.com/{a_type}/{account_name}/projects/{number}"


def handler():
    try:
        get_github_api()

        source_project_number = int(input("Enter source project #: "))

        # Fetch source project items
        source_project_id = fetch_project_node_id(
            SOURCE_ACCOUNT_TYPE,
            SOURCE_ACCOUNT_NAME,
            source_project_number,
        )

        items = fetch_all_project_items(source_project_id)
        new_project_name = get_project_name(source_project_id)

        # Create a new project in the target account
        target_owner_id = get_account_id(TARGET_ACCOUNT_TYPE, TARGET_ACCOUNT_NAME)
        new_project_id = create_new_project(target_owner_id, new_project_name)
        print(f"Created new project with ID: {new_project_id}")

        # Add items to the new project
        for item in items:
            if "content" not in item:
                print(f"Skipping empty item.")
                continue
            content = item["content"]
            if "id" in content:
                content_id = content["id"]
                add_item_to_project(new_project_id, content_id)
                print(f"Added item with ID {content_id} to new project.")

            else:
                # Handle draft issues
                draft_title = content["title"]
                draft_body = content["body"]
                create_draft_issue_in_project(new_project_id, draft_title, draft_body)
                print(f"Created draft issue with title '{draft_title}' in new project.")

        new_project_url = get_project_url(
            new_project_id,
            TARGET_ACCOUNT_TYPE,
            TARGET_ACCOUNT_NAME,
        )
        print("Project migration completed.")
        print(f"Visit new project and change visibility to `Public`: {new_project_url}")

    except Exception as e:
        print(f"An error occurred: {e} \n{traceback_format_exc()}")


if __name__ == "__main__":
    handler()