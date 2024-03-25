# How to contribute to Hyperion

Hyperion should prioritise working, agile code over strict standards, particularly for contributors that are not full time developers. The standards below are thus guidelines that developers should try to follow as much as possible (apart from when something is specified in bold, which is required).

General Workflow
----------------

1. An issue is created for the work. This issue should describe in as much detail as possible the work that needs to be done. Anyone is free to make a ticket and/or comment on one.
2. If a developer is going to do the work they assign themselves to the issue.
3. The developer makes a new branch with the format `issue_short_description` e.g. `122_create_a_contributing_file`. (External developers are also welcome to make forks)
4. The developer does the work on this branch, adding their work in small commits. Commit messages should be informative and prefixed with the issue number e.g. `(#122) Added contributing file`.
5. The developer submits a PR for the work. In the pull request should start with `Fixes #issue_num` e.g. `Fixes #122`, this will ensure the issue is automatically closed when the PR is merged. The developer should also add some background on how the reviewer might test the change.
6. If the developer has a particular person in mind to review the work they should assign that person to the PR as a reviewer.
7. The reviewer and developer go back and forth on the code until the reviewer approves it. (See [Reviewing Work](#reviewing-work))
8. Once the work is approved the original developer merges it.

**Work should not be done without an associated ticket describing what the work is**

Reviewing Work
--------------

**Work must be reviewed by another developer before it can be merged**. Remember that work is reviewed for a number of reasons:
* In order to maintain quality and avoid errors
* Help people learn

It is not a judgement on someone's technical abilities so be kind.

It is suggested that the reviewer prefixes comments with something like the following:
* **must**: A change that must be made before merging e.g. it will break something if not made
* **should/sugg**: A change that should be made e.g. definitely improves code quality but does not neccessarily break anything
* **nit**: A minor suggestion that the reviewer would like to see but is happy to leave as is e.g. rename a variable to something 

Developers are welcome to ignore **nit** comments if they wish and can choose not to do **should** comments but the must give a reason as to why they disagree with the change.

For minor changes to code reviewers are welcome to make the changes themselves but in this case the original developer should then recheck what the reviewer has done.
