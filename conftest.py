def pytest_addoption(parser):
    parser.addoption(
        "--debug-logging",
        action="store_true",
        default=False,
        help="initialise test loggers in DEBUG instead of INFO",
    )
