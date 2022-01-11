Workflow
====
Creating issues
----
Artemis issues are currently listed in the [MXGDA JIRA board](https://jira.diamond.ac.uk/projects/MXGDA/issues) under the `Artemis` tag.

Working on issues
----
1. Follow the standard MX GDA workflow for adding the JIRA ticket to the sprint etc.
2. Create a branch from main with the ticket number and a brief description e.g.:
    ```
    git checkout main
    git checkout -b MXGDA_3761_update_contributing_file
    ```
3. Complete the work on the ticket, making sure to follow the [coding standards](#coding-standards)
4. Commit regularly to the branch with commit messages that contain the ticket number and a description of the commit e.g.
    ```
    MXGDA 3761: Added a new contributing.md file
    ```
5. Once finished push the branch and create a pull request, ensuring you fill blank fields in the PR template
6. Request a reviewer(s) on your PR

Reviewing Work
---
1. Follow the review process as specified in the pull request
2. If there are minor changes required to the code (documentation etc.) feel free to add them yourself
3. Approve/reject the PR with any comments you have
4. Once one person has approved the PR and the CI has passed on it, the reviewer can merge the PR

Coding Standards
======
TBD
