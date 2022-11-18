"""Provides external interaction functionality to Artemis, including Nexus file
creation, ISPyB deposition, and Zocalo processing submissions.

Functionality from this module can/should be used through the callback functions in
external_interaction.communicator_callbacks which can subscribe to the Bluesky RunEngine
and handle these various interactions based on the documents emitted by the RunEngine
during the execution of the experimental plan.
"""
