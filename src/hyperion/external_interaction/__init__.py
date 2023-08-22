"""Provides external interaction functionality to Hyperion, including Nexus file
creation, ISPyB deposition, and Zocalo processing submissions.

Functionality from this module can/should be used through the callback functions in
external_interaction.callbacks which can subscribe to the Bluesky RunEngine and handle
these various interactions based on the documents emitted by the RunEngine during the
execution of the experimental plan. It's not recommended to use the interaction classes
here directly in plans except through the use of such callbacks.
"""
