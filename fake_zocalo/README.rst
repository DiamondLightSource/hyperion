fake_zocalo
===========================

.. note::

    This is meant to be used for testing artemis. Don't try to process any real
    data with it! You will just get back (1.2, 2.3, 3.4).

## To run:
- You first need to run `module load rabbitmq/dev`, which starts the rabbitmq server and generates some credentials in ~/.fake_zocalo
- And `module load dials/latest` in the shell running artemis, which allows the `devrmq` zocalo environment to be used