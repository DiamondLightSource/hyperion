Getting Started
===============

The Purpose of Dodal
--------------------

``dodal`` provides set of ophyd_ devices and bluesky_ plans that are commonly useful across many beamlines at DLS.

If you have some code that you think would be useful to be added please do so!

Using Devices
-------------

``dodal`` contains devices to cover anything you would like to do using a beamline's hardware.

To use these devices you can do the following::

    from dodal.beamlines import i03
    dcm = i03.dcm()
    # You can now use the DCM as you would any other device in Bluesky plans

If you are on a beamline workstation this will give you immediate access to the real hardware. If you are not on a 
beamline workstation it will default to connecting to a simulated instrument.

Adding Logging
--------------

``dodal`` provides some helper functions to help you log what's going on.

You can set these up using::
    
    from dodal.beamlines import i03
    from dodal.log import set_up_logging_handlers, LOGGER

    set_up_logging_handlers()
    
Some logging will now occur when you are using devices/plans, you can increase the amount of logs by 
instead using ``set_up_logging_handlers("DEBUG")``. You can also log more explicitly using::

    LOGGER.info("I am a log message")


If you are on a beamline workstation this will save any logs to ``dls_sw/BEAMLINE/logs/bluesky/`` and will
push them to graylog_. If you are not on a beamline workstation logs will be saved next to your working directory
and pushed to a local graylog instance.

If you would like to only log to graylog/file exlusively there are helper functions in ``dodal.log`` that you can use. 


.. _ophyd: https://nsls-ii.github.io/ophyd/
.. _bluesky: https://blueskyproject.io/bluesky/
.. _graylog: https://graylog2.diamond.ac.uk/search